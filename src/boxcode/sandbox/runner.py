"""执行 shell 命令的统一入口。模型要跑的每条命令都经过这里，不在 Agent 进程里直接 exec。"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# 传给命令的环境变量白名单。其他一律不传：模型的 API key、SSH_AUTH_SOCK、各种云凭证都在环境变量里
ENV_ALLOWLIST = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "SHELL", "VIRTUAL_ENV")


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


def run_process(argv: list[str], cwd: Path, timeout_s: int) -> CommandResult:
    try:
        p = subprocess.run(
            argv, cwd=cwd, env=clean_env(), capture_output=True, text=True,
            timeout=timeout_s, stdin=subprocess.DEVNULL, errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return CommandResult(exit_code=-1, stdout=out, stderr=err, timed_out=True)
    return CommandResult(exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)


def run_process_unsandboxed(command: str, cwd: Path, timeout_s: int) -> CommandResult:
    """只给评测框架自己的判分命令用，不给模型用。"""
    return run_process(["/bin/sh", "-c", command], cwd, timeout_s)


class NoSandboxRunner:
    """不隔离，只在非 macOS 上、用户显式传 --dangerously-no-sandbox 时使用。"""

    name = "none"

    def run(self, command: str, cwd: Path, timeout_s: int) -> CommandResult:
        return run_process(["/bin/sh", "-c", command], cwd, timeout_s)


def default_runner(workspace: Path, allow_network: bool, no_sandbox: bool = False) -> SandboxRunner:
    if no_sandbox:
        return NoSandboxRunner()
    if sys.platform != "darwin":
        raise RuntimeError("目前只实现了 macOS 的 Seatbelt 沙盒；其他系统请加 --dangerously-no-sandbox")
    from boxcode.sandbox.seatbelt import SeatbeltRunner

    return SeatbeltRunner(workspace, allow_network=allow_network)
