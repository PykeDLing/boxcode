"""沙盒真的在挡：这些测试会真实地起 sandbox-exec。"""

import contextlib
import http.server
import os
import re
import shutil
import signal
import socket
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
from boxcode.sandbox.runner import MAX_CAPTURE_BYTES
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
    # 把整个工作区挪走、在别处改 .git、再挪回来（红队实测能绕过“工作区里的 .git 只读”）
    'mv "$PWD" /private/tmp/bx$$ && printf "[core]\\n\\tfsmonitor = touch pwned\\n" >> /private/tmp/bx$$/.git/config;'
    ' mv /private/tmp/bx$$ "$PWD"',
    # 在临时目录里另建一个仓库也不行：.git 在哪儿都只读
    "git init -q /private/tmp/bx$$",
])
def test_cannot_change_git_dir(workspace: Path, cmd: str) -> None:
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    before = _snapshot(workspace / ".git")
    r = SeatbeltRunner(workspace).run(cmd, workspace, 10)
    assert r.exit_code != 0
    assert (workspace / ".git").is_dir() and not (workspace / "sub" / ".git").exists()
    assert _snapshot(workspace / ".git") == before  # 文件和内容都没变，不只是文件列表


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@macos_only
def test_nested_repo_cannot_be_moved_out_and_edited(workspace: Path) -> None:
    sub = workspace / "sub"
    subprocess.run(["git", "init", "-q", str(sub)], check=True)
    before = _snapshot(sub / ".git")
    SeatbeltRunner(workspace).run(
        'mv sub /private/tmp/sub$$ && echo x >> /private/tmp/sub$$/.git/config; mv /private/tmp/sub$$ sub',
        workspace, 10)
    assert _snapshot(sub / ".git") == before


@macos_only
def test_read_only_workspace_cannot_be_renamed_through_parent(workspace: Path) -> None:
    # read-only 模式下工作区本身改不了名，但以前它的上级目录可以（评测的临时目录就是这样）
    (workspace / "a.txt").write_text("keep")
    r = SeatbeltRunner(workspace, writable=False).run(
        'P=$(dirname "$PWD"); mv "$P" "$P-moved" && echo x > "$P-moved/ws/a.txt"; mv "$P-moved" "$P"',
        workspace, 10)
    assert r.exit_code != 0 and (workspace / "a.txt").read_text() == "keep"


@macos_only
def test_files_inside_workspace_still_creatable_and_removable(workspace: Path) -> None:
    r = SeatbeltRunner(workspace).run(
        "mkdir -p d/e && echo hi > d/e/f.txt && mv d/e/f.txt d/g.txt && rm -rf d && echo ok", workspace, 10)
    assert r.ok and r.stdout.strip() == "ok"


@macos_only
def test_git_read_commands_still_work(workspace: Path) -> None:
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    r = SeatbeltRunner(workspace).run("echo hi > a.txt && git status --short && touch .gitignore", workspace, 10)
    assert r.exit_code == 0 and "a.txt" in r.stdout


@macos_only
@pytest.mark.parametrize("rel", [
    ".ssh/id_rsa", ".zshrc", ".config/gh/hosts.yml",
    ".claude.json", ".config/anthropic/profile.json", ".ollama/id_ed25519", "Library/HTTPStorages/x",
])
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
    try:
        yield f"http://127.0.0.1:{srv.server_port}", hits
    finally:
        srv.shutdown()
        srv.server_close()


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
        seen = "\n".join(str(getattr(m, "content", "")) for m in llm.seen[-1])
        return seen, [e["decision"] for e in result.trace.of("tool_call")]

    seen, decisions = fooled(SeatbeltRunner(workspace, home=fake_home))
    assert decisions == ["allow"] * len(commands)  # 权限策略没拦，拦住的只能是沙盒
    assert canary not in seen and not hits
    # 对照：同样的命令不进沙盒，凭证就发出去了，说明上面拦住不是因为命令本身跑不通
    fooled(NoSandboxRunner())
    assert hits


def test_output_capture_is_bounded(workspace: Path) -> None:
    # 以前输出全部读进内存：`yes` 跑到超时能吃掉几个 GB
    for runner in _runners(workspace):
        r = runner.run("head -c 5000000 /dev/zero | tr '\\0' 'x'; echo END", workspace, 20)
        assert r.ok and len(r.stdout) < MAX_CAPTURE_BYTES + 200
        assert r.stdout.startswith("xxx") and r.stdout.rstrip().endswith("END") and "省略" in r.stdout


def test_endless_output_still_times_out(workspace: Path) -> None:
    for runner in _runners(workspace):
        t0 = time.monotonic()
        r = runner.run("yes", workspace, 1)
        assert r.timed_out and time.monotonic() - t0 < 5 and len(r.stdout) < MAX_CAPTURE_BYTES + 200


def test_cancel_kills_command(workspace: Path) -> None:
    for runner in _runners(workspace):
        cancel = threading.Event()
        threading.Timer(0.3, cancel.set).start()
        t0 = time.monotonic()
        r = runner.run("sleep 30 & echo $! > bg.pid; echo started; sleep 30", workspace, 60, cancel=cancel)
        assert r.cancelled and not r.timed_out and r.exit_code == -1 and "started" in r.stdout
        assert time.monotonic() - t0 < 5
        assert _wait_dead(int((workspace / "bg.pid").read_text()))


def test_waits_for_command_after_it_closes_its_output(workspace: Path) -> None:
    # 命令关掉了 stdout/stderr 但还在跑：要等它跑完，不能一看管道关了就杀掉
    for runner in _runners(workspace):
        r = runner.run("exec >/dev/null 2>&1; sleep 0.5; echo done > out.txt", workspace, 10)
        assert r.ok and (workspace / "out.txt").read_text().strip() == "done"


def test_extra_env_passed_but_secrets_are_not(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOXCODE_API_KEY", "sk-should-not-leak")
    for runner in _runners(workspace):
        r = runner.run("env", workspace, 10, env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in r.stdout and "sk-should-not-leak" not in r.stdout



@macos_only
def test_symlinked_dotfile_target_also_hidden(workspace: Path, tmp_path: Path) -> None:
    # 很多人用 dotfiles 仓库管理配置：~/.zshrc 是指向 ~/dotfiles/zshrc 的链接，Seatbelt 按解析后的路径匹配
    fake_home = (tmp_path / "home").resolve()
    (fake_home / "dotfiles").mkdir(parents=True)
    (fake_home / "dotfiles" / "zshrc").write_text("export OPENAI_API_KEY=SECRET")
    (fake_home / ".zshrc").symlink_to(fake_home / "dotfiles" / "zshrc")
    r = SeatbeltRunner(workspace, home=fake_home).run(f"cat '{fake_home}/.zshrc' '{fake_home}/dotfiles/zshrc'",
                                                      workspace, 10)
    assert "SECRET" not in r.stdout


def _lsregister() -> str:
    return ("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/"
            "lsregister")


@macos_only
def test_cannot_launch_apps_through_launchservices(workspace: Path) -> None:
    # `open` 让 LaunchServices 启动程序，起来的程序不在沙盒里（红队实测：完全逃出沙盒）
    marker = Path.home() / f".boxcode-lsopen-{uuid.uuid4().hex}"
    app = workspace / "Escape.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict>'
        "<key>CFBundleExecutable</key><string>escape</string>"
        f"<key>CFBundleIdentifier</key><string>dev.boxcode.test.{uuid.uuid4().hex}</string>"
        "<key>LSBackgroundOnly</key><true/></dict></plist>")
    exe = app / "Contents" / "MacOS" / "escape"
    exe.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    exe.chmod(0o755)
    try:
        r = SeatbeltRunner(workspace).run(f"open -g -j '{app}'; sleep 2", workspace, 15)
        time.sleep(1)
        assert not marker.exists(), r.stderr
    finally:
        marker.unlink(missing_ok=True)
        subprocess.run([_lsregister(), "-u", str(app)], capture_output=True)


@macos_only
def test_cannot_write_other_apps_preferences(workspace: Path) -> None:
    # 通过 cfprefsd 写 ~/Library/Preferences：能改终端的启动命令、别的程序的设置
    domain = f"dev.boxcode.test{uuid.uuid4().hex}"
    try:
        r = SeatbeltRunner(workspace).run(f"defaults write {domain} k v", workspace, 10)
        assert r.exit_code != 0
        assert subprocess.run(["defaults", "read", domain], capture_output=True).returncode != 0
    finally:
        subprocess.run(["defaults", "delete", domain], capture_output=True)
        (Path.home() / "Library" / "Preferences" / f"{domain}.plist").unlink(missing_ok=True)


@macos_only
def test_unix_sockets_only_inside_own_dirs(workspace: Path) -> None:
    # 系统临时目录、/private/var/run 里有别的程序的套接字（ssh-agent、浏览器），连上就能让它们替你干活
    path = f"/private/tmp/bx-{uuid.uuid4().hex[:8]}.sock"
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        srv.bind(path)
        srv.listen(1)
        connect = f"import socket; s = socket.socket(socket.AF_UNIX); s.connect({path!r}); print('connected')"
        r = SeatbeltRunner(workspace).run(f'{sys.executable} -c "{connect}"', workspace, 10)
        assert "connected" not in r.stdout
    finally:
        srv.close()
        Path(path).unlink(missing_ok=True)


@macos_only
def test_tools_using_sockets_in_tmpdir_still_work(workspace: Path) -> None:
    # multiprocessing.Manager 在 TMPDIR 里建 unix 套接字：沙盒给每个 runner 一个自己的 TMPDIR，那里放行
    code = "from multiprocessing import Manager; m = Manager(); d = m.dict(); d['a'] = 42; print(d['a']); m.shutdown()"
    r = SeatbeltRunner(workspace).run(f'{sys.executable} -c "{code}"', workspace, 60)
    assert r.ok and r.stdout.strip() == "42", r.stderr


@macos_only
def test_cannot_signal_processes_outside_sandbox(workspace: Path) -> None:
    outside = subprocess.Popen(["sleep", "30"])
    try:
        r = SeatbeltRunner(workspace).run(f"kill -TERM {outside.pid}; sleep 30 & kill $!; wait $!; echo $?",
                                          workspace, 10)
        assert outside.poll() is None  # 沙盒外的进程没被杀
        assert r.stdout.strip().endswith("143")  # 自己起的进程照样能杀
    finally:
        outside.kill()
        outside.wait()


@macos_only
def test_cannot_write_to_other_terminals(workspace: Path) -> None:
    # 以前整个 /dev 可写：能往你别的终端窗口里写转义序列
    master, slave = os.openpty()
    try:
        tty = os.ttyname(slave)
        r = SeatbeltRunner(workspace).run(f"printf INJECTED > {tty}", workspace, 10)
        assert r.exit_code != 0
        os.set_blocking(master, False)
        with contextlib.suppress(BlockingIOError):
            assert b"INJECTED" not in os.read(master, 1024)
        ok = SeatbeltRunner(workspace).run("echo a > /dev/null && echo b > /dev/stdout && echo c >&2", workspace, 10)
        assert ok.ok and ok.stdout.strip() == "b"
    finally:
        os.close(master)
        os.close(slave)


def test_profile_blocks_clipboard_and_keychain_services(workspace: Path) -> None:
    # 剪贴板和钥匙串只在规则里检查：实测要往你的剪贴板、钥匙串里放东西
    p = make_profile(workspace, Path.home(), allow_network=False)
    for service in ("com.apple.pasteboard.1", "com.apple.SecurityServer", "com.apple.secd"):
        assert f'(global-name "{service}")' in p
    assert "(deny lsopen)" in p and "(deny user-preference-write)" in p
    assert "(allow signal (target same-sandbox))" in p
    online = make_profile(workspace, Path.home(), allow_network=True)
    assert '(path-literal "/private/var/run/mDNSResponder")' in online and "(remote ip))" not in online


def test_multibyte_text_not_split_at_capture_boundary(workspace: Path) -> None:
    # 没超过上限时头尾要一起解码：分开解码会把跨在分界上的汉字劈成两个 U+FFFD
    r = NoSandboxRunner().run("python3 -c \"print('中' * 70000, end='')\"", workspace, 20)
    assert r.ok and r.stdout == "中" * 70000


def test_running_commands_killed_when_boxcode_exits(workspace: Path) -> None:
    # 关掉桌面窗口时，后台线程是 daemon，等不到 run_process 的 finally；以前判分里的 pytest 会一直跑下去
    script = (
        "import threading, time\n"
        "from pathlib import Path\n"
        "from boxcode.sandbox import NoSandboxRunner\n"
        f"ws = Path({str(workspace)!r})\n"
        "threading.Thread(target=NoSandboxRunner().run, args=('echo $$ > main.pid; sleep 41', ws, 60),"
        " daemon=True).start()\n"
        "while not (ws / 'main.pid').exists(): time.sleep(0.05)\n"
    )
    subprocess.run([sys.executable, "-c", script], check=True, timeout=30)
    assert _wait_dead(int((workspace / "main.pid").read_text()))


def test_normal_exit_near_deadline_is_not_a_timeout(workspace: Path) -> None:
    # 以前先判断超时再看主进程：快到超时才退出、后台进程还占着管道的，会被当成超时
    for runner in _runners(workspace):
        r = runner.run("sleep 5 & sleep 0.95; exit 3", workspace, 1)
        assert not r.timed_out and r.exit_code == 3
