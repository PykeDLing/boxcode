"""沙盒真的在挡：这些测试会真实地起 sandbox-exec。"""

import os
import subprocess
import uuid
from pathlib import Path

import pytest

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


@macos_only
def test_secrets_not_in_env(workspace: Path) -> None:
    os.environ["BOXCODE_API_KEY"] = "sk-should-not-leak"
    try:
        r = SeatbeltRunner(workspace).run("env", workspace, 10)
        assert "sk-should-not-leak" not in r.stdout
    finally:
        del os.environ["BOXCODE_API_KEY"]
