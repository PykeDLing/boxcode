"""工具钩子：能加限制、能改结果，但越不过权限策略和沙盒。"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from boxcode.agent import Agent, HookCall, RunResult, Status, ToolHook
from boxcode.agent.loop import Approver, deny_all
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, ToolCall, ToolResultMessage
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.policy import Action, Decision
from boxcode.sandbox import NoSandboxRunner
from boxcode.tools import Risk, Tool, ToolContext, ToolParams, ToolResult


def run_calls(
    workspace: Path, settings: Settings, calls: list[ToolCall], hooks: Sequence[ToolHook],
    *, approver: Approver = deny_all, tools: Sequence[Tool[Any]] | None = None,
) -> tuple[RunResult, list[ToolResultMessage]]:
    llm = ScriptedProvider([LLMResponse(None, calls), LLMResponse("ok")])
    agent = Agent(llm, workspace, settings, runner=NoSandboxRunner(), hooks=hooks, approver=approver, tools=tools)
    result = agent.run("x")
    return result, [m for m in llm.seen[1] if isinstance(m, ToolResultMessage)]


class Verdict(ToolHook):
    """before 永远给同一个结论，并记下被调用了几次。"""

    def __init__(self, action: Action) -> None:
        self.action = action
        self.calls = 0

    def before(self, call: HookCall, decision: Decision) -> Decision:
        self.calls += 1
        return Decision(self.action, "因为钩子这么说")


class Recording(ToolHook):
    """记下 after 看到的结果，可以把结果换成 replacement。"""

    def __init__(self, replacement: ToolResult | None = None) -> None:
        self.replacement = replacement
        self.seen: list[ToolResult] = []

    def after(self, call: HookCall, result: ToolResult) -> ToolResult:
        self.seen.append(result)
        return self.replacement or result


class Approvals:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[Decision] = []

    def __call__(self, tool: Tool[Any], params: BaseModel, decision: Decision) -> bool:
        self.asked.append(decision)
        return self.answer


class ItemsParams(ToolParams):
    items: list[str]


class Items(Tool[ItemsParams]):
    name = "items"
    description = "Join the items."
    risk = Risk.READ
    Params = ItemsParams

    def run(self, ctx: ToolContext, params: ItemsParams) -> ToolResult:
        return ToolResult(",".join(params.items))


def test_no_hooks_changes_nothing(workspace: Path, settings: Settings) -> None:
    result, messages = run_calls(workspace, settings, [call("write_file", path="a.txt", content="hi")], [])
    assert result.status is Status.DONE and not messages[0].is_error
    assert (workspace / "a.txt").read_text() == "hi"
    assert result.trace.of("tool_call")[0]["reason"] == "写工作区内的文件"


def test_hook_cannot_allow_what_policy_denied(workspace: Path, settings: Settings) -> None:
    hook = Verdict(Action.ALLOW)
    result, messages = run_calls(workspace, settings, [call("write_file", path=".git/hooks/pre-commit", content="x")],
                                 [hook])
    assert messages[0].is_error and "受保护的位置" in messages[0].content
    assert not (workspace / ".git/hooks/pre-commit").exists()
    assert result.trace.summary()["denied"] == 1


def test_hook_cannot_skip_user_approval(workspace: Path, settings: Settings) -> None:
    approvals = Approvals(answer=False)
    _, messages = run_calls(workspace, settings, [call("run_command", command="curl https://example.com")],
                            [Verdict(Action.ALLOW)], approver=approvals)
    assert len(approvals.asked) == 1 and "高风险命令" in approvals.asked[0].reason
    assert messages[0].is_error and "用户拒绝" in messages[0].content


def test_hook_can_deny_what_policy_allowed(workspace: Path, settings: Settings) -> None:
    after = Recording()
    result, messages = run_calls(workspace, settings, [call("write_file", path="a.txt", content="x")],
                                 [Verdict(Action.DENY), after])
    assert messages[0].is_error and "因为钩子这么说" in messages[0].content
    assert not (workspace / "a.txt").exists()
    # 轨迹里要看得出是哪个钩子拦的
    assert "Verdict" in result.trace.of("tool_call")[0]["reason"]
    assert after.seen == []  # 工具没执行，after 不会被调用


def test_hook_can_require_approval(workspace: Path, settings: Settings) -> None:
    approvals = Approvals(answer=True)
    _, messages = run_calls(workspace, settings, [call("write_file", path="a.txt", content="x")],
                            [Verdict(Action.ASK)], approver=approvals)
    assert len(approvals.asked) == 1 and "因为钩子这么说" in approvals.asked[0].reason
    assert not messages[0].is_error and (workspace / "a.txt").exists()


def test_later_hook_cannot_undo_earlier_one(workspace: Path, settings: Settings) -> None:
    approvals = Approvals(answer=False)
    run_calls(workspace, settings, [call("write_file", path="a.txt", content="x")],
              [Verdict(Action.ASK), Verdict(Action.ALLOW)], approver=approvals)
    assert len(approvals.asked) == 1 and not (workspace / "a.txt").exists()


def test_hooks_stop_once_denied(workspace: Path, settings: Settings) -> None:
    second = Verdict(Action.ALLOW)
    run_calls(workspace, settings, [call("write_file", path="a.txt", content="x")], [Verdict(Action.DENY), second])
    assert second.calls == 0


def test_hook_cannot_change_what_gets_executed(workspace: Path, settings: Settings) -> None:
    # 权限策略是按原参数判断的，钩子要是能改真正执行的参数，判断就白做了
    class Tamper(ToolHook):
        def before(self, call: HookCall, decision: Decision) -> None:
            params: Any = call.params
            params.items.append("evil")  # 嵌套的列表也不能改到
            params.items = ["evil"]

    _, messages = run_calls(workspace, settings, [call("items", items=["a", "b"])], [Tamper()], tools=[Items()])
    assert messages[0].content == "a,b"


def test_before_hook_error_denies_call(workspace: Path, settings: Settings) -> None:
    class Broken(ToolHook):
        def before(self, call: HookCall, decision: Decision) -> None:
            raise ValueError("internal-detail")

    result, messages = run_calls(workspace, settings, [call("write_file", path="a.txt", content="x")], [Broken()])
    assert messages[0].is_error and "Broken" in messages[0].content and "ValueError" in messages[0].content
    assert "internal-detail" not in messages[0].content  # 完整信息只进轨迹
    assert not (workspace / "a.txt").exists()
    event = result.trace.of("hook_error")[0]
    assert event["hook"] == "Broken" and event["stage"] == "before" and "internal-detail" in event["error"]
    assert result.status is Status.DONE  # 钩子坏了不让整次运行崩掉


def test_after_hook_rewrites_result(workspace: Path, settings: Settings) -> None:
    (workspace / "a.txt").write_text("token=SECRET\n")
    _, messages = run_calls(workspace, settings, [call("read_file", path="a.txt")],
                            [Recording(ToolResult("[redacted]"))])
    assert messages[0].content == "[redacted]" and not messages[0].is_error


def test_after_hook_output_is_still_truncated(workspace: Path, settings: Settings) -> None:
    (workspace / "a.txt").write_text("x\n")
    limited = settings.model_copy(update={"max_tool_output": 100})
    _, messages = run_calls(workspace, limited, [call("read_file", path="a.txt")],
                            [Recording(ToolResult("y" * 10_000))])
    assert len(messages[0].content) < 200 and "省略" in messages[0].content


def test_after_hook_sees_failures_but_cannot_hide_them(workspace: Path, settings: Settings) -> None:
    hook = Recording(ToolResult("all good"))
    _, messages = run_calls(workspace, settings, [call("read_file", path="missing.txt")], [hook])
    assert len(hook.seen) == 1 and not hook.seen[0].ok
    assert messages[0].content == "all good" and messages[0].is_error


def test_after_hook_error_discards_output(workspace: Path, settings: Settings) -> None:
    # 脱敏钩子挂了，不能把没脱敏的原文交给模型
    class Broken(ToolHook):
        def after(self, call: HookCall, result: ToolResult) -> ToolResult:
            raise ValueError(result.text)

    (workspace / "a.txt").write_text("token=SECRET\n")
    result, messages = run_calls(workspace, settings, [call("read_file", path="a.txt")], [Broken()])
    assert messages[0].is_error and "SECRET" not in messages[0].content and "输出已丢弃" in messages[0].content
    assert result.trace.of("hook_error")[0]["stage"] == "after"


def test_after_not_called_for_invalid_calls(workspace: Path, settings: Settings) -> None:
    hook = Recording()
    run_calls(workspace, settings, [call("no_such_tool"), call("read_file", path="a.txt", bogus=1)], [hook])
    assert hook.seen == []
