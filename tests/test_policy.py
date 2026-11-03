from pathlib import Path

import pytest

from boxcode.policy import Action, ApprovalMode, Policy
from boxcode.tools.base import Risk, Target


@pytest.fixture
def policy(workspace: Path) -> Policy:
    return Policy(ApprovalMode.WORKSPACE_WRITE, workspace)


def test_read_always_allowed(policy: Policy) -> None:
    assert policy.check(Risk.READ, Target()).action is Action.ALLOW


def test_write_in_workspace_allowed(policy: Policy, workspace: Path) -> None:
    assert policy.check(Risk.WRITE, Target(paths=[workspace / "a.py"])).action is Action.ALLOW


def test_git_hooks_protected(policy: Policy, workspace: Path) -> None:
    d = policy.check(Risk.WRITE, Target(paths=[workspace / ".git/hooks/pre-commit"]))
    assert d.action is Action.DENY


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


def test_full_auto_allows_risky(workspace: Path) -> None:
    p = Policy(ApprovalMode.FULL_AUTO, workspace)
    assert p.check(Risk.EXEC, Target(command="curl x")).action is Action.ALLOW
