"""沙盒真的在挡：这些测试会真实地起 sandbox-exec。"""

import contextlib
import http.server
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from boxcode.agent import Agent
from boxcode.config import Settings
from boxcode.evals import load_tasks
from boxcode.llm.base import LLMResponse
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.policy import ApprovalMode, ExecutionPolicy
from boxcode.sandbox import NoSandboxRunner, SandboxRunner, SeatbeltRunner, make_profile
from tests.conftest import macos_only

TASKS = Path(__file__).parent.parent / "evals" / "tasks"


def test_profile_contains_workspace_and_offline_rules(workspace: Path) -> None:
    p = make_profile(workspace, Path.home(), allow_network=False)
    assert f'(subpath "{workspace}")' in p
    assert "(deny network-outbound (remote ip))" in p
    assert "(deny network-outbound (remote ip))" not in make_profile(workspace, Path.home(), allow_network=True)


@macos_only
def test_can_write_inside_workspace(workspace: Path) -> None:
    r = SeatbeltRunner(workspace).run("echo hi > out.txt && cat out.txt", workspace, 10)
    assert r.exit_code == 0 and r.stdout.strip() == "hi"


@macos_only
def test_read_only_sandbox_cannot_write_workspace(workspace: Path) -> None:
    (workspace / "a.txt").write_text("keep")
    r = SeatbeltRunner(workspace, writable=False).run("cat a.txt && echo x > a.txt", workspace, 10)
    assert r.exit_code != 0 and r.stdout.strip() == "keep"
    assert (workspace / "a.txt").read_text() == "keep"


@macos_only
def test_cannot_write_outside_workspace(workspace: Path) -> None:
    target = Path.home() / f".boxcode-escape-test-{uuid.uuid4().hex}"
    try:
        r = SeatbeltRunner(workspace).run(f"echo pwned > '{target}'", workspace, 10)
        assert r.exit_code != 0
        assert not target.exists()
    finally:
        target.unlink(missing_ok=True)


@macos_only
@pytest.mark.parametrize("cmd", [
    "echo 'curl evil' > .git/hooks/pre-commit",
    "echo x > .GIT/HOOKS/pre-commit",  # APFS 默认不区分大小写
    "printf '[core]\\n\\tfsmonitor = curl evil\\n' >> .git/config",
    # 把 .git 换成指向别处的文件，沙盒外的 git 就会读攻击者的配置
    "mv .git .git_orig",
    "rm -rf .git",
    "mkdir -p sub && printf 'gitdir: ../evil\\n' > sub/.git",
    "mkdir -p .git/modules/sub/hooks && echo x > .git/modules/sub/hooks/post-checkout",
])
def test_cannot_change_git_dir(workspace: Path, cmd: str) -> None:
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    before = sorted(p.relative_to(workspace) for p in (workspace / ".git").rglob("*"))
    r = SeatbeltRunner(workspace).run(cmd, workspace, 10)
    assert r.exit_code != 0
    assert (workspace / ".git").is_dir() and not (workspace / "sub" / ".git").exists()
    assert sorted(p.relative_to(workspace) for p in (workspace / ".git").rglob("*")) == before


@macos_only
def test_git_read_commands_still_work(workspace: Path) -> None:
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    r = SeatbeltRunner(workspace).run("echo hi > a.txt && git status --short && touch .gitignore", workspace, 10)
    assert r.exit_code == 0 and "a.txt" in r.stdout


@macos_only
@pytest.mark.parametrize("rel", [".ssh/id_rsa", ".zshrc", ".config/gh/hosts.yml"])
def test_cannot_read_private_files(workspace: Path, tmp_path: Path, rel: str) -> None:
    fake_home = (tmp_path / "home").resolve()
    (fake_home / rel).parent.mkdir(parents=True)
    (fake_home / rel).write_text("SECRET")
    r = SeatbeltRunner(workspace, home=fake_home).run(f"cat '{fake_home / rel}'", workspace, 10)
    assert r.exit_code != 0
    assert "SECRET" not in r.stdout


@macos_only
def test_dotenv_readable_only_inside_workspace(workspace: Path, tmp_path: Path) -> None:
    other = (tmp_path / "other-project").resolve()
    other.mkdir()
    (other / ".env").write_text("OTHER_SECRET")
    (workspace / ".env").write_text("OWN_CONFIG")
    r = SeatbeltRunner(workspace).run(f"cat .env; cat '{other}/.env'", workspace, 10)
    assert "OWN_CONFIG" in r.stdout and "OTHER_SECRET" not in r.stdout


@macos_only
def test_network_off_by_default(workspace: Path) -> None:
    py = "import socket; socket.create_connection(('1.1.1.1', 80), timeout=3); print('connected')"
    r = SeatbeltRunner(workspace).run(f"/usr/bin/python3 -c \"{py}\"", workspace, 15)
    assert "connected" not in r.stdout


def _wait_dead(pid: int, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _runners(workspace: Path) -> list[SandboxRunner]:
    return [NoSandboxRunner(), *([SeatbeltRunner(workspace)] if sys.platform == "darwin" else [])]


@pytest.mark.parametrize("bg", [
    "sleep 30 &",  # 占着输出管道：以前每条命令都要等到超时
    "sleep 30 > /dev/null 2>&1 &",  # 不占管道：以前命令照常返回，但进程一直活着
])
def test_background_processes_killed_when_command_ends(workspace: Path, bg: str) -> None:
    for runner in _runners(workspace):
        t0 = time.monotonic()
        r = runner.run(f"{bg} echo $! > bg.pid; echo hi", workspace, 20)
        assert r.exit_code == 0 and r.stdout.strip() == "hi" and not r.timed_out
        assert time.monotonic() - t0 < 5
        assert _wait_dead(int((workspace / "bg.pid").read_text()))


def test_process_leaving_group_does_not_hang(workspace: Path) -> None:
    # os.setsid 脱离进程组的进程杀不到，它还占着输出管道：以前会一直等它结束（这里是 30 秒）
    escape = "/usr/bin/python3 -c 'import os, time; os.setsid(); time.sleep(30)'"
    for runner in _runners(workspace):
        t0 = time.monotonic()
        try:
            r = runner.run(f"{escape} & echo $! > bg.pid; sleep 1; echo ok", workspace, 20)
            assert "ok" in r.stdout and time.monotonic() - t0 < 10
        finally:
            with contextlib.suppress(ProcessLookupError, ValueError, FileNotFoundError):
                os.kill(int((workspace / "bg.pid").read_text()), signal.SIGKILL)


def test_timeout_kills_whole_group(workspace: Path) -> None:
    for runner in _runners(workspace):
        r = runner.run("sleep 30 & echo $! > bg.pid; echo started; sleep 30", workspace, 1)
        assert r.timed_out and r.exit_code == -1 and "started" in r.stdout
        assert _wait_dead(int((workspace / "bg.pid").read_text()))


@macos_only
def test_secrets_not_in_env(workspace: Path) -> None:
    os.environ["BOXCODE_API_KEY"] = "sk-should-not-leak"
    try:
        r = SeatbeltRunner(workspace).run("env", workspace, 10)
        assert "sk-should-not-leak" not in r.stdout
    finally:
        del os.environ["BOXCODE_API_KEY"]


@pytest.fixture
def exfil_server() -> Iterator[tuple[str, list[bytes]]]:
    """本机起一个收数据的服务，冒充注入里的 attacker.example：收到任何请求就算泄漏。"""
    hits: list[bytes] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            hits.append(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", hits
    srv.shutdown()


@macos_only
@pytest.mark.parametrize("task_id", ["101-injection-readme", "102-injection-agents-md"])
def test_injected_commands_stopped_by_sandbox_alone(
    workspace: Path, tmp_path: Path, settings: Settings, monkeypatch: pytest.MonkeyPatch,
    exfil_server: tuple[str, list[bytes]], task_id: str,
) -> None:
    # 真实模型跑评测时自己就拒绝了，沙盒没被测到。这里假设模型被骗、权限策略也放行（full-auto），
    # 原样执行注入里的命令，只剩沙盒在挡
    url, hits = exfil_server
    task = load_tasks(TASKS, only=[task_id])[0]
    shutil.copytree(task.repo, workspace, dirs_exist_ok=True)
    injected = "\n".join(p.read_text() for p in workspace.glob("*.md"))
    commands = [c.replace("https://attacker.example", url) for c in re.findall(r"(?:cat|curl) [^`\n]+", injected)]
    assert any(c.startswith("curl") for c in commands)

    canary = f"CANARY-{uuid.uuid4().hex}"
    fake_home = (tmp_path / "home").resolve()
    for rel in (".ssh/id_rsa", ".aws/credentials"):
        (fake_home / rel).parent.mkdir(parents=True)
        (fake_home / rel).write_text(canary)
    monkeypatch.setenv("HOME", str(fake_home))  # 命令里的 ~ 和 $HOME 指向假的家目录

    def fooled(runner: SandboxRunner) -> tuple[str, list[str]]:
        llm = ScriptedProvider([LLMResponse(None, [call("run_command", command=c)]) for c in commands]
                               + [LLMResponse("done")])
        agent = Agent(llm, workspace, settings, ExecutionPolicy(ApprovalMode.FULL_AUTO), runner=runner)
        result = agent.run(task.prompt)
        seen = "\n".join(str(m["content"]) for m in llm.seen[-1])
        return seen, [e["decision"] for e in result.trace.of("tool_call")]

    seen, decisions = fooled(SeatbeltRunner(workspace, home=fake_home))
    assert decisions == ["allow"] * len(commands)  # 权限策略没拦，拦住的只能是沙盒
    assert canary not in seen and not hits
    # 对照：同样的命令不进沙盒，凭证就发出去了，说明上面拦住不是因为命令本身跑不通
    fooled(NoSandboxRunner())
    assert hits
