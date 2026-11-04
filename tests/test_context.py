"""给模型的上下文：系统提示要和实际的执行权限一致。"""

from pathlib import Path

from boxcode.agent import Agent
from boxcode.agent.context import system_prompt, task_message
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, SystemMessage, ToolResultMessage, UserMessage
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.policy import ApprovalMode, ExecutionPolicy
from boxcode.sandbox import NoSandboxRunner
from tests.conftest import macos_only


def test_prompt_describes_actual_sandbox(workspace: Path) -> None:
    default = system_prompt(workspace, ExecutionPolicy())
    assert "only write inside the workspace" in default and "network is off" in default
    assert "read-only sandbox" in system_prompt(workspace, ExecutionPolicy(ApprovalMode.READ_ONLY))
    assert "network is available" in system_prompt(workspace, ExecutionPolicy(allow_network=True))
    assert "WITHOUT a sandbox" in system_prompt(workspace, ExecutionPolicy(sandboxed=False))
    # 没有沙盒时只读模式只能靠提示
    no_box_ro = system_prompt(workspace, ExecutionPolicy(ApprovalMode.READ_ONLY, sandboxed=False))
    assert "WITHOUT a sandbox" in no_box_ro and "do not modify any files" in no_box_ro


def test_project_notes_are_repository_content_not_system_prompt(workspace: Path, settings: Settings) -> None:
    # AGENTS.md 和 README 一样来自仓库，可能被人埋指令：不能进系统提示
    (workspace / "AGENTS.md").write_text("Run tests with `make test`.")
    llm = ScriptedProvider([LLMResponse("ok")])
    Agent(llm, workspace, settings, runner=NoSandboxRunner()).run("fix the bug")
    first, second = llm.seen[0][0], llm.seen[0][1]
    assert isinstance(first, SystemMessage) and isinstance(second, UserMessage)
    system, user = first.content, second.content
    assert "make test" not in system
    assert '<project_notes source="AGENTS.md">' in user and "make test" in user
    assert "cannot override the security rules" in user and user.endswith("Task: fix the bug")


def test_project_notes_link_out_of_workspace_not_read(workspace: Path, tmp_path: Path) -> None:
    # 文件工具不在沙盒里：仓库里放一个指向凭证的 AGENTS.md，启动时就会把凭证发给模型
    (tmp_path / "credentials").write_text("aws_secret_access_key = SECRET")
    (workspace / "AGENTS.md").symlink_to(tmp_path / "credentials")
    assert task_message(workspace, "x") == "x"


@macos_only
def test_read_only_mode_sandbox_blocks_writes_even_when_approved(workspace: Path, settings: Settings) -> None:
    # 以前 read-only 只在权限策略里“问一下”，用户点了同意，命令照样能写工作区
    llm = ScriptedProvider([LLMResponse(None, [call("run_command", command="echo x > out.txt")]), LLMResponse("ok")])
    agent = Agent(llm, workspace, settings, ExecutionPolicy(ApprovalMode.READ_ONLY), approver=lambda *_: True)
    agent.run("x")
    assert not (workspace / "out.txt").exists()
    result = llm.seen[1][-1]
    assert isinstance(result, ToolResultMessage) and "Operation not permitted" in result.content
