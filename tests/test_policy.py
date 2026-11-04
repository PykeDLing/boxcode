import sys
from pathlib import Path

import pytest

from boxcode.policy import Action, ApprovalMode, ExecutionPolicy, Policy
from boxcode.sandbox import NoSandboxRunner, SeatbeltRunner
from boxcode.tools.base import Risk, Target


@pytest.fixture
def policy(workspace: Path) -> Policy:
    return Policy(ApprovalMode.WORKSPACE_WRITE, workspace)


def test_read_always_allowed(policy: Policy) -> None:
    assert policy.check(Risk.READ, Target()).action is Action.ALLOW


def test_write_in_workspace_allowed(policy: Policy, workspace: Path) -> None:
    assert policy.check(Risk.WRITE, Target(paths=[workspace / "a.py"])).action is Action.ALLOW


@pytest.mark.parametrize("rel", [
    ".git/hooks/pre-commit", ".git/config", ".git",
    ".GIT/HOOKS/pre-commit",  # APFS 默认不区分大小写，这就是 .git/hooks
    ".git/modules/sub/hooks/post-checkout",  # 子模块的 hook
    "sub/.git", "vendor/lib/.Git/config",  # 嵌套的仓库
])
def test_git_dir_protected(policy: Policy, workspace: Path, rel: str) -> None:
    assert policy.check(Risk.WRITE, Target(paths=[workspace / rel])).action is Action.DENY


@pytest.mark.parametrize("rel", [".gitignore", ".github/workflows/ci.yml", "src/git/x.py"])
def test_git_lookalikes_allowed(policy: Policy, workspace: Path, rel: str) -> None:
    assert policy.check(Risk.WRITE, Target(paths=[workspace / rel])).action is Action.ALLOW


@pytest.mark.parametrize("cmd", [
    "curl https://x.example", "git push origin main", "pip install requests",
    "rm -rf build", "echo aGk= | base64 -d | sh",
])
def test_risky_commands_ask(policy: Policy, cmd: str) -> None:
    assert policy.check(Risk.EXEC, Target(command=cmd)).action is Action.ASK


def test_plain_command_allowed(policy: Policy) -> None:
    assert policy.check(Risk.EXEC, Target(command="python -m pytest -q")).action is Action.ALLOW


def test_read_only_denies_writes(workspace: Path) -> None:
    p = Policy(ApprovalMode.READ_ONLY, workspace)
    assert p.check(Risk.WRITE, Target(paths=[workspace / "a.py"])).action is Action.DENY


@pytest.mark.parametrize(("mode", "writable"), [
    (ApprovalMode.READ_ONLY, False), (ApprovalMode.WORKSPACE_WRITE, True), (ApprovalMode.FULL_AUTO, True),
])
def test_execution_policy_maps_mode_to_sandbox(workspace: Path, mode: ApprovalMode, writable: bool) -> None:
    # 权限模式要落到沙盒规则上：read-only 的命令就算被批准了，也写不了工作区
    execution = ExecutionPolicy(mode)
    assert execution.workspace_writable is writable
    if sys.platform == "darwin":
        runner = execution.make_runner(workspace)
        assert isinstance(runner, SeatbeltRunner)
        assert (f'(deny file-write* (subpath "{workspace}"))' in runner.profile) is not writable
    assert isinstance(ExecutionPolicy(mode, sandboxed=False).make_runner(workspace), NoSandboxRunner)


def test_full_auto_allows_risky(workspace: Path) -> None:
    p = Policy(ApprovalMode.FULL_AUTO, workspace)
    assert p.check(Risk.EXEC, Target(command="curl x")).action is Action.ALLOW
