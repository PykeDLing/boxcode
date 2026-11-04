"""执行 shell 命令的统一入口。模型要跑的每条命令都经过这里，不在 Agent 进程里直接 exec。"""

import atexit
import contextlib
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Protocol

from boxcode.sandbox.procs import kill_sandbox

# 传给命令的环境变量白名单。其他一律不传：模型的 API key、SSH_AUTH_SOCK、各种云凭证都在环境变量里
ENV_ALLOWLIST = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "SHELL", "VIRTUAL_ENV")

# 每隔这么久看一次：主进程退出没有、超时没有、有没有被取消
POLL_S = 0.1
# 主进程结束（或被杀）后，最多再等这么久把管道里剩下的输出读完
DRAIN_S = 2.0
# stdout、stderr 各最多保留这么多字节（开头一半、结尾一半）：`yes` 这种命令不会把内存撑爆
MAX_CAPTURE_BYTES = 256 * 1024
READ_CHUNK = 64 * 1024


def clean_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
    return {**env, **(extra or {})}


@dataclass(frozen=True)
class CommandResult:
    exit_code: int  # 被信号 N 杀掉时是 -N；超时、被取消时是 -1。判断超时和取消看下面两个字段，不要看退出码
    stdout: str
    stderr: str
    timed_out: bool = False
    cancelled: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.cancelled


class SandboxRunner(Protocol):
    @property
    def name(self) -> str: ...

    def run(
        self, command: str, cwd: Path, timeout_s: float, *,
        cancel: threading.Event | None = None, env: Mapping[str, str] | None = None, pass_fds: Sequence[int] = (),
    ) -> CommandResult:
        """pass_fds：交给命令的文件描述符（编号不变）。它们归命令所有：启动之后（启动失败也一样）父进程这边的会被关掉。"""
        ...


class _Capture:
    """只留开头和结尾各 limit/2 字节，中间的丢掉并记下丢了多少。"""

    def __init__(self, limit: int) -> None:
        self.half = limit // 2
        self.head = bytearray()
        self.tail = bytearray()
        self.dropped = 0

    def add(self, chunk: bytes) -> None:
        room = self.half - len(self.head)
        if room > 0:
            self.head += chunk[:room]
            chunk = chunk[room:]
        self.tail += chunk
        if len(self.tail) > self.half:
            extra = len(self.tail) - self.half
            del self.tail[:extra]
            self.dropped += extra

    def text(self) -> str:
        if not self.dropped:  # 一起解码：分开解码会把跨在头尾分界上的多字节字符劈成两个 U+FFFD
            return bytes(self.head + self.tail).decode(errors="replace")
        head = self.head.decode(errors="replace")
        tail = self.tail.decode(errors="replace")
        return f"{head}\n\n... [省略 {self.dropped} 字节] ...\n\n{tail}"


def _kill_all(pgid: int, sandbox_marker: str | None) -> None:
    """杀掉整个进程组；在 Seatbelt 沙盒里跑的，再把沙盒里剩下的进程（脱离了进程组的）也杀掉。"""
    with contextlib.suppress(ProcessLookupError, PermissionError):  # 进程组已经空了
        os.killpg(pgid, signal.SIGKILL)
    if sandbox_marker is not None:
        kill_sandbox(sandbox_marker)


# 正在跑的命令：进程组 → 沙盒标记。BoxCode 退出时（例如关掉桌面窗口，后台线程是 daemon，等不到它们的 finally）
# 全部杀掉，否则判分里死循环的 pytest 会在 BoxCode 退出后一直跑下去：超时是父进程管的，父进程已经没了
_live: dict[int, str | None] = {}
_live_lock = threading.Lock()


@atexit.register
def _kill_live() -> None:
    with _live_lock:
        for pgid, marker in list(_live.items()):
            _kill_all(pgid, marker)


def run_process(
    argv: list[str], cwd: Path, timeout_s: float, *,
    cancel: threading.Event | None = None, env: Mapping[str, str] | None = None,
    max_capture_bytes: int = MAX_CAPTURE_BYTES, sandbox_marker: str | None = None, pass_fds: Sequence[int] = (),
) -> CommandResult:
    """执行命令并收集输出。

    - 命令放在单独的进程组里，主进程一结束（或超时、被取消）就整组杀掉：它留在后台的进程（`sleep 100 &`、
      开了没关的服务器）不会占着输出管道让命令一直等到超时，也不会在 Agent 接下来用文件工具时还在后台改文件
    - sandbox_marker：命令在带这个标记的 Seatbelt 沙盒里（见 procs.py）。用 setsid、setpgid 脱离了进程组的
      进程也一起杀掉。不用沙盒时（--dangerously-no-sandbox）这种进程杀不到，它可能还占着管道，
      所以收尾最多再读 DRAIN_S 秒
    - 两个管道在同一个线程里用 selectors 读，输出只保留开头和结尾，内存占用有上限
    - pass_fds 交给子进程后在这边关掉：比如判分时两个进程之间的管道，一边退出了另一边才读得到 EOF
    """
    try:
        p = subprocess.Popen(
            argv, cwd=cwd, env=clean_env(env), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, pass_fds=tuple(pass_fds),
        )
    finally:
        for fd in pass_fds:
            os.close(fd)
    with _live_lock:
        _live[p.pid] = sandbox_marker
    pipes: list[IO[bytes]] = [p.stdout, p.stderr]  # type: ignore[list-item]  # 传了 PIPE，一定不是 None
    out, err = _Capture(max_capture_bytes), _Capture(max_capture_bytes)
    deadline = time.monotonic() + timeout_s
    drain_until: float | None = None  # 主进程结束后才有：读到这个时间点为止
    timed_out = cancelled = False
    sel = selectors.DefaultSelector()
    try:
        for f, capture in zip(pipes, (out, err), strict=True):
            os.set_blocking(f.fileno(), False)
            sel.register(f, selectors.EVENT_READ, capture)
        while True:
            now = time.monotonic()
            if drain_until is None:
                # 先看主进程是不是已经退出：快到超时才正常退出（后台进程还占着管道）的，不能算成超时
                exited = p.poll() is not None
                timed_out = not exited and now >= deadline
                cancelled = not exited and not timed_out and cancel is not None and cancel.is_set()
                if exited or timed_out or cancelled:
                    _kill_all(p.pid, sandbox_marker)
                    drain_until = now + DRAIN_S
            elif now >= drain_until or not sel.get_map():
                break
            if not sel.get_map():
                # 输出管道都关了，主进程还在跑（例如 `exec >/dev/null; 长任务`）：接着等它结束
                with contextlib.suppress(subprocess.TimeoutExpired):
                    p.wait(timeout=POLL_S)
                continue
            for key, _ in sel.select(timeout=POLL_S):
                chunk = os.read(key.fd, READ_CHUNK)
                if chunk:
                    key.data.add(chunk)
                else:
                    sel.unregister(key.fileobj)
    finally:
        _kill_all(p.pid, sandbox_marker)
        sel.close()
        for f in pipes:
            f.close()
        p.wait()
        with _live_lock:
            _live.pop(p.pid, None)
    stdout, stderr = out.text(), err.text()
    interrupted = timed_out or cancelled
    return CommandResult(exit_code=-1 if interrupted else p.returncode, stdout=stdout, stderr=stderr,
                         timed_out=timed_out, cancelled=cancelled)


class NoSandboxRunner:
    """不隔离，只在非 macOS 上、用户显式传 --dangerously-no-sandbox 时使用。"""

    name = "none"

    def run(
        self, command: str, cwd: Path, timeout_s: float, *,
        cancel: threading.Event | None = None, env: Mapping[str, str] | None = None, pass_fds: Sequence[int] = (),
    ) -> CommandResult:
        return run_process(["/bin/sh", "-c", command], cwd, timeout_s, cancel=cancel, env=env, pass_fds=pass_fds)


def default_runner(
    workspace: Path, allow_network: bool, writable: bool = True, no_sandbox: bool = False,
) -> SandboxRunner:
    if no_sandbox:
        return NoSandboxRunner()
    if sys.platform != "darwin":
        raise RuntimeError("目前只实现了 macOS 的 Seatbelt 沙盒；其他系统请加 --dangerously-no-sandbox")
    from boxcode.sandbox.seatbelt import SeatbeltRunner

    return SeatbeltRunner(workspace, allow_network=allow_network, writable=writable)
