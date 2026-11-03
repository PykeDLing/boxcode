"""执行 shell 命令的统一入口。模型要跑的每条命令都经过这里，不在 Agent 进程里直接 exec。"""

import contextlib
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# 传给命令的环境变量白名单。其他一律不传：模型的 API key、SSH_AUTH_SOCK、各种云凭证都在环境变量里
ENV_ALLOWLIST = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "SHELL", "VIRTUAL_ENV")

# 等命令结束时，每隔这么久看一次主进程是不是已经退出
POLL_S = 0.1
# 进程组杀掉后，最多再等这么久把剩下的输出读完
DRAIN_S = 2


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class SandboxRunner(Protocol):
    name: str

    def run(self, command: str, cwd: Path, timeout_s: int) -> CommandResult: ...


def _kill_group(pgid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):  # 进程组已经空了
        os.killpg(pgid, signal.SIGKILL)


def _text(data: str | bytes | None) -> str:
    return data.decode(errors="replace") if isinstance(data, bytes) else (data or "")


def _drain(p: subprocess.Popen[str]) -> tuple[str, str]:
    """进程组杀掉后读完剩下的输出。用 os.setsid 脱离了进程组的进程杀不到，它可能还占着管道，
    所以最多再等 DRAIN_S 秒，之后关掉管道，只要已经读到的部分。"""
    try:
        return p.communicate(timeout=DRAIN_S)
    except subprocess.TimeoutExpired as e:
        for f in (p.stdout, p.stderr):
            if f is not None:
                f.close()
        p.wait()
        return _text(e.stdout), _text(e.stderr)


def run_process(argv: list[str], cwd: Path, timeout_s: int) -> CommandResult:
    """执行命令并收集输出。

    命令放在单独的进程组里，结束或超时后整组杀掉：它留在后台的进程（`sleep 100 &`、开了没关的服务器）
    不会占着输出管道让命令一直等到超时，也不会在 Agent 接下来用文件工具时还在后台改文件。
    """
    p = subprocess.Popen(
        argv, cwd=cwd, env=clean_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, errors="replace", start_new_session=True,
    )
    deadline = time.monotonic() + timeout_s
    timed_out = False
    try:
        while True:
            try:
                out, err = p.communicate(timeout=POLL_S)
                break
            except subprocess.TimeoutExpired:
                # 超时，或者主进程已经退出、只剩后台进程占着管道：都不再等
                timed_out = time.monotonic() >= deadline
                if timed_out or p.poll() is not None:
                    _kill_group(p.pid)
                    out, err = _drain(p)
                    break
    finally:
        _kill_group(p.pid)
    return CommandResult(exit_code=-1 if timed_out else p.returncode, stdout=out, stderr=err, timed_out=timed_out)


class NoSandboxRunner:
    """不隔离，只在非 macOS 上、用户显式传 --dangerously-no-sandbox 时使用。"""

    name = "none"

    def run(self, command: str, cwd: Path, timeout_s: int) -> CommandResult:
        return run_process(["/bin/sh", "-c", command], cwd, timeout_s)


def default_runner(
    workspace: Path, allow_network: bool, writable: bool = True, no_sandbox: bool = False,
) -> SandboxRunner:
    if no_sandbox:
        return NoSandboxRunner()
    if sys.platform != "darwin":
        raise RuntimeError("目前只实现了 macOS 的 Seatbelt 沙盒；其他系统请加 --dangerously-no-sandbox")
    from boxcode.sandbox.seatbelt import SeatbeltRunner

    return SeatbeltRunner(workspace, allow_network=allow_network, writable=writable)
