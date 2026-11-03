"""沙盒真的在挡：这些测试会真实地起 sandbox-exec。"""

import os
import uuid
from pathlib import Path

from boxcode.sandbox import SeatbeltRunner, make_profile
from tests.conftest import macos_only


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
def test_cannot_write_outside_workspace(workspace: Path) -> None:
    target = Path.home() / f".boxcode-escape-test-{uuid.uuid4().hex}"
    try:
        r = SeatbeltRunner(workspace).run(f"echo pwned > '{target}'", workspace, 10)
        assert r.exit_code != 0
        assert not target.exists()
    finally:
        target.unlink(missing_ok=True)


@macos_only
def test_cannot_change_git_hooks(workspace: Path) -> None:
    (workspace / ".git" / "hooks").mkdir(parents=True)
    r = SeatbeltRunner(workspace).run("echo 'curl evil' > .git/hooks/pre-commit", workspace, 10)
    assert r.exit_code != 0
    assert not (workspace / ".git" / "hooks" / "pre-commit").exists()


@macos_only
def test_cannot_read_private_dirs(workspace: Path, tmp_path: Path) -> None:
    fake_home = (tmp_path / "home").resolve()
    (fake_home / ".ssh").mkdir(parents=True)
    (fake_home / ".ssh" / "id_rsa").write_text("SECRET")
    r = SeatbeltRunner(workspace, home=fake_home).run(f"cat '{fake_home}/.ssh/id_rsa'", workspace, 10)
    assert r.exit_code != 0
    assert "SECRET" not in r.stdout


@macos_only
def test_network_off_by_default(workspace: Path) -> None:
    py = "import socket; socket.create_connection(('1.1.1.1', 80), timeout=3); print('connected')"
    r = SeatbeltRunner(workspace).run(f"/usr/bin/python3 -c \"{py}\"", workspace, 15)
    assert "connected" not in r.stdout


@macos_only
def test_secrets_not_in_env(workspace: Path) -> None:
    os.environ["BOXCODE_API_KEY"] = "sk-should-not-leak"
    try:
        r = SeatbeltRunner(workspace).run("env", workspace, 10)
        assert "sk-should-not-leak" not in r.stdout
    finally:
        del os.environ["BOXCODE_API_KEY"]
