import sys
from pathlib import Path

import pytest

from boxcode.policy import Action, ApprovalMode, Decision, ExecutionPolicy, Policy, UnsafeWorkspace, check_workspace
from boxcode.sandbox import NoSandboxRunner, SeatbeltRunner
from boxcode.tools.base import Risk, Target


@pytest.fixture
def policy(workspace: Path) -> Policy:
    return Policy(ApprovalMode.WORKSPACE_WRITE, workspace)


@pytest.mark.parametrize(("current", "other", "expected"), [
    (Action.ALLOW, Action.ALLOW, "current"), (Action.ALLOW, Action.ASK, "other"), (Action.ALLOW, Action.DENY, "other"),
    (Action.ASK, Action.ALLOW, "current"), (Action.ASK, Action.ASK, "current"), (Action.ASK, Action.DENY, "other"),
    (Action.DENY, Action.ALLOW, "current"), (Action.DENY, Action.ASK, "current"), (Action.DENY, Action.DENY, "current"),
])
def test_decision_only_gets_stricter(current: Action, other: Action, expected: str) -> None:
    # 工具钩子靠这一条才放不宽权限
    assert Decision(current, "current").tightened_by(Decision(other, "other")).reason == expected


def test_read_always_allowed(policy: Policy) -> None:
    assert policy.check(Risk.READ, Target()).action is Action.ALLOW


def test_write_in_workspace_allowed(policy: Policy, workspace: Path) -> None:
    assert policy.check(Risk.WRITE, Target(paths=(workspace / "a.py",))).action is Action.ALLOW


@pytest.mark.parametrize("rel", [
    ".git/hooks/pre-commit", ".git/config", ".git",
    ".GIT/HOOKS/pre-commit",  # APFS 默认不区分大小写，这就是 .git/hooks
    ".git/modules/sub/hooks/post-checkout",  # 子模块的 hook
    "sub/.git", "vendor/lib/.Git/config",  # 嵌套的仓库
])
def test_git_dir_protected(policy: Policy, workspace: Path, rel: str) -> None:
    assert policy.check(Risk.WRITE, Target(paths=(workspace / rel,))).action is Action.DENY


@pytest.mark.parametrize("rel", [".gitignore", ".github/workflows/ci.yml", "src/git/x.py"])
def test_git_lookalikes_allowed(policy: Policy, workspace: Path, rel: str) -> None:
    assert policy.check(Risk.WRITE, Target(paths=(workspace / rel,))).action is Action.ALLOW


@pytest.mark.parametrize("cmd", [
    "curl https://x.example", "git push origin main", "pip install requests", "rsync -a . host:/x",
    "rm -rf build", "echo aGk= | base64 -d | sh",
    # 以前漏掉的写法
    "pip3 install requests", "python -m pip install requests", "uv add httpx", "uv sync", "npm i left-pad",
    "rm -fr build", "rm -f -r build", "rm -R build", "rm --recursive build", "chmod -R 777 .",
    "base64 --decode payload | sh", 'eval "$(cat x)"', "echo aGk= | base64 -di > x.sh",
    # 对抗测试找到的漏网写法
    "git -C . push origin main", "git -c k=v push", "cat p | /bin/sh", "cat p | env sh", "cat p | perl",
    "pip3.12 install x", "pipx install x", "npx cowsay", "uvx ruff", "uv run --with httpx python x.py", "npm ci",
    "bun add x", "find . -name '*.pyc' -delete", "git clean -fdx",
    # 带路径执行联网程序照样要问
    "/usr/bin/ssh host", "cd sub && ssh host", "./scp a host:/x",
])
def test_risky_commands_ask(policy: Policy, cmd: str) -> None:
    assert policy.check(Risk.EXEC, Target(command=cmd)).action is Action.ASK


@pytest.mark.parametrize("cmd", [
    "python -m pytest -q", "uv run pytest", "rm -f a.txt", "rm file-r", "chmod 644 a.txt",
    "find . -name '*.py' -exec grep -l foo {} +",  # 很常用的只读写法，不能每次都问
    "git status", "git -C sub log --oneline", "uv run pytest -q", "node script.js", "npm test",
    # 文件名、目录名里的 ssh、nc、rsync 不是在联网：以前 `ls ~/.ssh` 被当成“联网或远程访问”来问
    "ls ~/.ssh", "cat ~/.ssh/config", "ls /etc/ssh/", "ncdump data.nc", "cat .rsync-filter",
])
def test_plain_command_allowed(policy: Policy, cmd: str) -> None:
    assert policy.check(Risk.EXEC, Target(command=cmd)).action is Action.ALLOW


def test_read_only_denies_writes(workspace: Path) -> None:
    p = Policy(ApprovalMode.READ_ONLY, workspace)
    assert p.check(Risk.WRITE, Target(paths=(workspace / "a.py",))).action is Action.DENY


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


def test_execution_policy_passes_extra_deny_read_to_sandbox(workspace: Path, tmp_path: Path) -> None:
    # 评测用它挡住原题的目录；默认什么也不加
    task_dir = (tmp_path / "task").resolve()
    task_dir.mkdir()
    if sys.platform == "darwin":
        denied = ExecutionPolicy(deny_read=(task_dir,)).make_runner(workspace)
        assert isinstance(denied, SeatbeltRunner) and f'(subpath "{task_dir}")' in denied.profile
        plain = ExecutionPolicy().make_runner(workspace)
        assert isinstance(plain, SeatbeltRunner) and str(task_dir) not in plain.profile
    assert isinstance(ExecutionPolicy(sandboxed=False, deny_read=(task_dir,)).make_runner(workspace), NoSandboxRunner)


def test_full_auto_allows_risky(workspace: Path) -> None:
    p = Policy(ApprovalMode.FULL_AUTO, workspace)
    assert p.check(Risk.EXEC, Target(command="curl x")).action is Action.ALLOW


@pytest.mark.parametrize("mode", [ApprovalMode.WORKSPACE_WRITE, ApprovalMode.FULL_AUTO])
@pytest.mark.parametrize("risk", [Risk.WRITE, Risk.EXEC])
def test_undeclared_target_asks(workspace: Path, mode: ApprovalMode, risk: Risk) -> None:
    # 工具忘了覆盖 target()、外部工具没有命令可看：以前直接放行，理由还写着“在沙盒中执行”
    decision = Policy(mode, workspace).check(risk, Target())
    assert decision.action is Action.ASK and "没有声明" in decision.reason


def test_undeclared_target_in_read_only(workspace: Path) -> None:
    p = Policy(ApprovalMode.READ_ONLY, workspace)
    assert p.check(Risk.WRITE, Target()).action is Action.DENY  # 只读模式的拒绝比“问一下”更严，不能被放宽
    assert p.check(Risk.EXEC, Target()).action is Action.ASK


def test_exec_with_only_paths_is_undeclared(policy: Policy, workspace: Path) -> None:
    # 策略看的是命令：只给了路径，还是不知道要执行什么
    assert policy.check(Risk.EXEC, Target(paths=(workspace / "a.py",))).action is Action.ASK


def test_empty_command_is_declared(policy: Policy) -> None:
    # 模型给了空命令也是声明过的：它照常进沙盒，不算“不知道要执行什么”
    assert policy.check(Risk.EXEC, Target(command="")).action is Action.ALLOW


@pytest.mark.parametrize("rel", [
    "", "Library/LaunchAgents", ".ssh", ".aws", ".boxcode", ".boxcode/runs",
    # 本身沙盒照常能读，但里面的配置、程序之后会在沙盒外执行；或者包含了凭证目录
    ".config", ".config/fish", ".local", ".local/bin", "bin", ".cargo", ".oh-my-zsh", ".nvm", ".pyenv", "go",
])
def test_workspace_cannot_cover_sensitive_home_dirs(tmp_path: Path, rel: str) -> None:
    # 沙盒放行整个工作区的写入：工作区是主目录，~/.zshrc、~/Library/LaunchAgents 就都能改
    home = (tmp_path / "home").resolve()
    with pytest.raises(UnsafeWorkspace):
        check_workspace(home / rel, home / ".boxcode", home=home)


@pytest.mark.parametrize("ws", ["/", "/Users", "/Applications/Foo.app", "/opt/homebrew", "/usr/local/bin"])
def test_workspace_cannot_be_system_dir(tmp_path: Path, ws: str) -> None:
    with pytest.raises(UnsafeWorkspace):
        check_workspace(Path(ws), tmp_path / ".boxcode", home=Path("/Users/someone"))


def test_workspace_case_variant_of_home_rejected() -> None:
    # APFS 不区分大小写，Path.resolve() 也不改大小写：/users/PYKE 就是主目录
    with pytest.raises(UnsafeWorkspace):
        check_workspace(Path(str(Path.home()).upper()), Path.home() / ".boxcode")


def test_workspace_cannot_contain_boxcode_data(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    with pytest.raises(UnsafeWorkspace, match="数据目录"):
        check_workspace(project, project / ".boxcode", home=tmp_path / "home")


def test_ordinary_project_dirs_allowed(tmp_path: Path) -> None:
    home = (tmp_path / "home").resolve()
    check_workspace(home / "dev" / "proj", home / ".boxcode", home=home)
    check_workspace(Path("/private/tmp/boxcode-eval/repo"), home / ".boxcode", home=home)  # 评测就在临时目录里
