"""主循环：用剧本模型走完“改代码 → 自检失败 → 再改 → 通过”，以及各种结束方式。"""

import shutil
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import Field

from boxcode.agent import Agent, Status, deny_all
from boxcode.agent.loop import Approver
from boxcode.config import Settings
from boxcode.llm.base import (
    LLMCancelled,
    LLMResponse,
    LLMUnavailable,
    Message,
    StopReason,
    SystemMessage,
    ToolResultMessage,
    ToolSpec,
    UserMessage,
)
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.policy import UnsafeWorkspace
from boxcode.sandbox import NoSandboxRunner
from boxcode.tools import Risk, Tool, ToolContext, ToolParams, ToolResult, default_tools

CHECK = "grep -q 'value = 3' app.py"


def make_agent(
    llm: ScriptedProvider, workspace: Path, settings: Settings, *, tools: Sequence[Tool[Any]] | None = None,
    cancel: threading.Event | None = None, approver: Approver = deny_all,
) -> Agent:
    return Agent(llm, workspace, settings, runner=NoSandboxRunner(), tools=tools, cancel=cancel, approver=approver)


def tool_results(messages: Sequence[Message]) -> list[ToolResultMessage]:
    return [m for m in messages if isinstance(m, ToolResultMessage)]


def test_edit_then_done(workspace: Path, settings: Settings) -> None:
    (workspace / "app.py").write_text("value = 1\n")
    llm = ScriptedProvider([
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 1", new_string="value = 3")]),
        LLMResponse("Changed value to 3."),
    ])
    result = make_agent(llm, workspace, settings).run("set value to 3", verify_command=CHECK)
    assert result.status is Status.DONE and result.final_message == "Changed value to 3."
    assert (workspace / "app.py").read_text() == "value = 3\n"
    assert result.trace.summary()["tool_calls"] == 1
    assert result.trace.path is not None and result.trace.path.exists()
    assert [e["event"] for e in result.trace.events] == ["run_start", "llm_call", "tool_call", "llm_call", "verify",
                                                         "run_end"]
    assert isinstance(llm.seen[0][0], SystemMessage) and isinstance(llm.seen[0][1], UserMessage)
    assert {t.name for t in llm.tools} == {t.name for t in default_tools()}


def test_verify_failure_is_fed_back(workspace: Path, settings: Settings) -> None:
    (workspace / "app.py").write_text("value = 1\n")
    llm = ScriptedProvider([
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 1", new_string="value = 2")]),
        LLMResponse("Done."),  # 自检失败
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 2", new_string="value = 3")]),
        LLMResponse("Fixed."),
    ])
    result = make_agent(llm, workspace, settings).run("set value to 3", verify_command=CHECK)
    assert result.status is Status.DONE and result.fix_rounds == 1
    feedback = llm.seen[2][-1]
    assert isinstance(feedback, UserMessage) and "failed (exit code 1)" in feedback.content
    # 自检输出来自仓库里的测试，以用户身份交回去时要标成数据
    assert "<check_output>" in feedback.content and "not instructions" in feedback.content


def test_verify_gives_up_after_max_fix_rounds(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse("done")] * 5)
    agent = make_agent(llm, workspace, settings.model_copy(update={"max_fix_rounds": 1}))
    result = agent.run("x", verify_command="false")
    assert result.status is Status.VERIFY_FAILED and result.fix_rounds == 1 and result.turns == 2


def test_denied_and_invalid_calls_reach_model(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([
        LLMResponse(None, [
            call("write_file", path=".git/hooks/pre-commit", content="evil"),
            call("read_file", path="../outside"),
            call("no_such_tool"),
            call("read_file", path="a.txt", bogus=1),  # 多给的参数直接报错，而不是悄悄忽略
        ]),
        LLMResponse("ok"),
    ])
    result = make_agent(llm, workspace, settings).run("x")
    results = tool_results(llm.seen[1])
    assert "拒绝" in results[0].content
    assert "不在工作区" in results[1].content
    assert "没有这个工具" in results[2].content and "read_file" in results[2].content
    assert "参数不对" in results[3].content and "bogus" in results[3].content
    assert all(r.is_error for r in results)
    assert result.trace.summary()["denied"] == 1
    assert not (workspace / ".git/hooks/pre-commit").exists()


class BoomParams(ToolParams):
    size: int = Field(default=0)


class Boom(Tool[BoomParams]):
    """测试用的工具：size=0 时抛没预料到的异常，否则返回 size 个字符。"""

    name = "boom"
    description = "test tool"
    risk = Risk.READ
    Params = BoomParams

    def run(self, ctx: ToolContext, params: BoomParams) -> ToolResult:
        if not params.size:
            raise RuntimeError("disk on fire")
        return ToolResult("x" * params.size)


def test_unexpected_tool_error_reaches_model(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse(None, [call("boom")]), LLMResponse("gave up")])
    result = make_agent(llm, workspace, settings, tools=[Boom()]).run("x")
    assert result.status is Status.DONE
    msg = tool_results(llm.seen[1])[0]
    assert msg.is_error and "RuntimeError: disk on fire" in msg.content
    # 轨迹里要分得清：这是工具没预料到的异常，不是模型用错了参数
    assert result.trace.of("tool_call")[0]["exception"] == "RuntimeError"


def test_every_tool_output_truncated_centrally(workspace: Path, settings: Settings) -> None:
    # 单个工具忘了截断（例如 grep 1000 条、list_dir 2000 项），也撑不爆上下文
    llm = ScriptedProvider([LLMResponse(None, [call("boom", size=50_000)]), LLMResponse("ok")])
    make_agent(llm, workspace, settings, tools=[Boom()]).run("x")
    content = tool_results(llm.seen[1])[0].content
    assert len(content) < settings.max_tool_output + 100 and "省略" in content


class Unavailable:
    name = "down"

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: object = None) -> LLMResponse:
        raise LLMUnavailable("Claude 接口错误 529：overloaded")


class Buggy:
    name = "buggy"

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: object = None) -> LLMResponse:
        raise KeyError("tool_use_id")  # Provider 自己没处理到的异常


def test_llm_error_ends_run_with_trace(workspace: Path, settings: Settings) -> None:
    result = Agent(Unavailable(), workspace, settings, runner=NoSandboxRunner()).run("x")
    assert result.status is Status.ERROR and result.final_message and "529" in result.final_message
    assert result.trace.of("run_end")[0]["status"] == "error"


def test_bug_in_boxcode_ends_run_as_crashed(workspace: Path, settings: Settings) -> None:
    # BoxCode 自己的 bug：照样留下 run_end 和完整的异常栈，不抛给调用方
    result = Agent(Buggy(), workspace, settings, runner=NoSandboxRunner()).run("x")
    assert result.status is Status.CRASHED and result.final_message and "KeyError" in result.final_message
    end = result.trace.of("run_end")[0]
    assert end["status"] == "crashed" and "Traceback" in end["traceback"]


def test_refusal_stops_without_running_tools(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse(None, [call("write_file", path="x", content="y")],
                                        stop_reason=StopReason.REFUSAL)])
    result = make_agent(llm, workspace, settings).run("x")
    assert result.status is Status.REFUSED
    assert not (workspace / "x").exists()


def test_truncated_tool_calls_not_executed(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([
        LLMResponse(None, [call("write_file", path="big.txt", content="half")], stop_reason=StopReason.MAX_TOKENS),
        LLMResponse("ok"),
    ])
    make_agent(llm, workspace, settings).run("write")
    assert not (workspace / "big.txt").exists()
    msg = tool_results(llm.seen[1])[0]
    assert msg.is_error and "max_tokens" in msg.content


def test_max_turns(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse(None, [call("list_dir")]) for _ in range(5)])
    result = make_agent(llm, workspace, settings.model_copy(update={"max_turns": 3})).run("loop forever")
    assert result.status is Status.MAX_TURNS and result.turns == 3


def test_cancel_before_start_calls_no_model(workspace: Path, settings: Settings) -> None:
    cancel = threading.Event()
    cancel.set()
    llm = ScriptedProvider([LLMResponse("never")])
    result = make_agent(llm, workspace, settings, cancel=cancel).run("x")
    assert result.status is Status.CANCELLED and not llm.seen
    assert result.trace.of("run_end")[0]["status"] == "cancelled"


def test_cancel_skips_remaining_tool_calls(workspace: Path, settings: Settings) -> None:
    # 停止时这一轮还没执行的工具调用不再执行（以前 full-auto 下会全部照常执行）
    cancel = threading.Event()

    def approve_then_stop(*_: object) -> bool:
        cancel.set()
        return False

    llm = ScriptedProvider([
        LLMResponse(None, [call("run_command", command="curl x"), call("write_file", path="later.txt", content="x")]),
        LLMResponse("never"),
    ])
    result = make_agent(llm, workspace, settings, cancel=cancel, approver=approve_then_stop).run("x")
    assert result.status is Status.CANCELLED and len(llm.seen) == 1
    assert not (workspace / "later.txt").exists()


def test_cancel_kills_running_command(workspace: Path, settings: Settings) -> None:
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    llm = ScriptedProvider([LLMResponse(None, [call("run_command", command="sleep 30")]), LLMResponse("never")])
    result = make_agent(llm, workspace, settings, cancel=cancel).run("x")
    assert result.status is Status.CANCELLED
    tool = result.trace.of("tool_call")[0]
    assert tool["duration_s"] < 5 and not tool["ok"]


def test_agent_runs_only_once(workspace: Path, settings: Settings) -> None:
    agent = make_agent(ScriptedProvider([LLMResponse("ok")]), workspace, settings)
    agent.run("x")
    with pytest.raises(RuntimeError, match="只能运行一次"):
        agent.run("again")


def test_unsafe_workspace_refused(settings: Settings) -> None:
    # 沙盒放行整个工作区的写入：把主目录当工作区，等于把 ~/.zshrc 交给模型
    with pytest.raises(UnsafeWorkspace):
        make_agent(ScriptedProvider([]), Path.home(), settings)


def test_trace_write_failure_does_not_crash_run(workspace: Path, settings: Settings) -> None:
    # 轨迹是旁路记录：目录被删、磁盘满了，运行照样结束、照样返回结果
    class DeletesRuns(ScriptedProvider):
        def complete(
            self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: object = None,
        ) -> LLMResponse:
            shutil.rmtree(settings.runs_dir)
            settings.runs_dir.parent.chmod(0o500)  # 也建不回来
            return super().complete(messages, tools)

    try:
        result = make_agent(DeletesRuns([LLMResponse("ok")]), workspace, settings).run("x")
    finally:
        settings.runs_dir.parent.chmod(0o700)
    assert result.status is Status.DONE and result.trace.write_error
    assert [e["event"] for e in result.trace.events][-1] == "run_end"


class Hanging:
    """模型接口卡住不返回，也不理会 cancel（例如不用流式的 OpenAI 兼容接口）。放开之后要调用工具写文件。"""

    name = "hanging"

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.cancel_seen: object = None

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: object = None) -> LLMResponse:
        self.cancel_seen = cancel
        self.entered.set()
        self.release.wait(30)
        return LLMResponse(None, [call("write_file", path="late.txt", content="x")])


def test_stop_does_not_wait_for_model_call(workspace: Path, settings: Settings) -> None:
    # 以前按停止要等这次模型调用返回（Claude 一次回复可能要几分钟），界面一直显示“运行中”
    llm, cancel = Hanging(), threading.Event()
    agent = Agent(llm, workspace, settings, runner=NoSandboxRunner(), cancel=cancel)
    results: list[Any] = []
    worker = threading.Thread(target=lambda: results.append(agent.run("x")))
    worker.start()
    try:
        assert llm.entered.wait(10)
        cancel.set()
        worker.join(3)
        assert not worker.is_alive()
        assert results[0].status is Status.CANCELLED and "模型调用" in results[0].final_message
        assert llm.cancel_seen is cancel  # Provider 拿到了 cancel，能做到的（Claude 的流式接口）会自己断开
    finally:
        llm.release.set()
    time.sleep(0.3)
    assert not (workspace / "late.txt").exists()  # 停止之后才回来的回复被丢掉，它要的工具不执行
    assert [e["event"] for e in results[0].trace.events][-1] == "run_end"


class Cooperative:
    name = "cooperative"

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: object = None) -> LLMResponse:
        raise LLMCancelled  # Provider 自己先发现了停止


def test_provider_noticing_cancel_ends_run_as_cancelled(workspace: Path, settings: Settings) -> None:
    result = Agent(Cooperative(), workspace, settings, runner=NoSandboxRunner()).run("x")
    assert result.status is Status.CANCELLED
