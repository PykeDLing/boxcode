"""Claude 的格式转换。不发请求，只测转换、回复解析和读流。"""

import contextlib
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest
from anthropic.types.beta import BetaMessage

from boxcode.agent import Agent
from boxcode.config import Settings
from boxcode.llm import claude as claude_module
from boxcode.llm.base import (
    AssistantMessage,
    LLMCancelled,
    LLMResponse,
    Native,
    ServerCompaction,
    StopReason,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
    clears_tool_results,
)
from boxcode.llm.claude import (
    PROVIDER,
    AnthropicProvider,
    convert_messages,
    convert_tools,
    parse_response,
    read_stream,
    server_compaction,
    strip_before_fallback,
)
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.sandbox import NoSandboxRunner
from boxcode.tools import default_tools

Block = dict[str, Any]
THINKING: Block = {"type": "thinking", "thinking": "", "signature": "sig-abc"}
TOOL_USE: Block = {"type": "tool_use", "id": "toolu_1", "name": "list_dir", "input": {"path": "."}}


def test_tools_converted_with_eager_streaming() -> None:
    tools = convert_tools([t.spec() for t in default_tools()])
    edit = next(t for t in tools if t["name"] == "edit_file")
    assert edit["input_schema"]["required"] == ["path", "old_string", "new_string"]
    # 多给的参数在 Schema 里就写明不允许
    assert edit["input_schema"]["additionalProperties"] is False
    assert all(t["eager_input_streaming"] for t in tools)


def test_parallel_tool_results_merged_into_one_user_message() -> None:
    raw = [THINKING, TOOL_USE, {**TOOL_USE, "id": "toolu_2"}]
    system, msgs = convert_messages([
        SystemMessage("SYS"),
        UserMessage("task"),
        AssistantMessage(None, native=Native(PROVIDER, raw)),
        ToolResultMessage("toolu_1", "a"),
        ToolResultMessage("toolu_2", "boom", is_error=True),
        UserMessage("check failed"),
    ])
    assert system == "SYS"
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "user"]
    assert msgs[1]["content"] is raw  # 原样回传，思考块一个不少
    results = msgs[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_1", "toolu_2"]
    assert "is_error" not in results[0] and results[1]["is_error"] is True


def test_assistant_from_other_provider_rebuilt() -> None:
    _, msgs = convert_messages([
        UserMessage("x"),
        AssistantMessage("looking", (ToolCall("c1", "grep", '{"pattern": "a"}'), ToolCall("c2", "grep", "{bad")),
                         native=Native("openai", "ignored")),
    ])
    assert msgs[1]["content"] == [
        {"type": "text", "text": "looking"},
        {"type": "tool_use", "id": "c1", "name": "grep", "input": {"pattern": "a"}},
        # 别的模型给的参数不是合法 JSON：那次调用已经作为错误回给了模型，这里只要能发出去
        {"type": "tool_use", "id": "c2", "name": "grep", "input": {}},
    ]


def test_parse_response_keeps_raw_blocks() -> None:
    blocks = [THINKING, {"type": "text", "text": "Let me look."}, TOOL_USE]
    r = parse_response(blocks, "tool_use", Usage(10, 5, 8))
    assert r.content == "Let me look." and r.stop_reason is StopReason.END
    assert r.tool_calls[0].name == "list_dir" and json.loads(r.tool_calls[0].arguments) == {"path": "."}
    assert not r.truncated
    msg = r.to_message()
    assert msg.native == Native(PROVIDER, blocks) and msg.tool_calls == tuple(r.tool_calls)


def test_stop_reasons() -> None:
    assert parse_response([TOOL_USE], "max_tokens", Usage()).truncated
    assert parse_response([TOOL_USE], "model_context_window_exceeded", Usage()).truncated
    assert not parse_response([{"type": "text", "text": "long"}], "max_tokens", Usage()).truncated  # 没有工具调用
    assert parse_response([], "refusal", Usage()).stop_reason is StopReason.REFUSAL


def test_blocks_before_fallback_dropped() -> None:
    blocks = [THINKING, {"type": "text", "text": "partial"}, TOOL_USE,
              {"type": "fallback"}, {"type": "text", "text": "rest"}, {**TOOL_USE, "id": "toolu_9"}]
    kept = strip_before_fallback(blocks)
    assert [b["type"] for b in kept] == ["text", "fallback", "text", "tool_use"]
    assert [c.id for c in parse_response(blocks, "tool_use", Usage()).tool_calls] == ["toolu_9"]


class FakeStream:
    """按顺序吐出事件；cancel_after 不是 None 时，吐出这么多个事件之后模拟用户按了停止。"""

    def __init__(self, events: int, cancel: threading.Event, cancel_after: int | None = None) -> None:
        self.events, self.cancel, self.cancel_after = events, cancel, cancel_after
        self.read = 0

    def __iter__(self) -> Iterator[object]:
        for i in range(self.events):
            if i == self.cancel_after:
                self.cancel.set()
            self.read += 1
            yield {"type": "content_block_delta"}

    def get_final_message(self) -> BetaMessage:
        return BetaMessage.model_validate({
            "id": "msg_1", "type": "message", "role": "assistant", "model": "m", "content": [],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        })


def test_stream_read_to_end_without_cancel() -> None:
    stream = FakeStream(5, threading.Event())
    assert read_stream(stream, stream.cancel).stop_reason == "end_turn" and stream.read == 5


def test_stream_abandoned_as_soon_as_cancelled() -> None:
    # 按停止后不再读剩下的事件：外面的 with 关掉连接，服务器停止生成，剩下的输出不再计费
    stream = FakeStream(1000, threading.Event(), cancel_after=3)
    with pytest.raises(LLMCancelled):
        read_stream(stream, stream.cancel)
    assert stream.read == 4


class FinishedStream:
    def __init__(self, final: BetaMessage) -> None:
        self.final = final

    def __iter__(self) -> Iterator[object]:
        return iter(())

    def get_final_message(self) -> BetaMessage:
        return self.final


class FakeMessages:
    """记下 stream 的参数，返回的消息里带着 context_management 的结果。"""

    def __init__(self, applied: list[dict[str, Any]]) -> None:
        self.kwargs: dict[str, Any] = {}
        self.applied = applied

    @contextlib.contextmanager
    def stream(self, **kwargs: Any) -> Iterator[FinishedStream]:
        self.kwargs = kwargs
        final = BetaMessage.model_validate({
            "id": "msg_1", "type": "message", "role": "assistant", "model": "m", "content": [],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
            "context_management": {"applied_edits": self.applied},
        })
        yield FinishedStream(final)


def claude_provider(
    monkeypatch: pytest.MonkeyPatch, threshold: int, applied: list[dict[str, Any]] | None = None,
) -> tuple[AnthropicProvider, FakeMessages]:
    fake = FakeMessages(applied or [])
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)
    return AnthropicProvider(Settings(provider="anthropic", context_compact_tokens=threshold)), fake


def test_context_editing_requested_with_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, fake = claude_provider(monkeypatch, 12000)
    assert clears_tool_results(provider)
    provider.complete([UserMessage("x")], [])
    assert fake.kwargs["betas"] == [claude_module.FALLBACK_BETA, claude_module.CONTEXT_EDITING_BETA]
    edit = fake.kwargs["context_management"]["edits"][0]
    assert edit["type"] == "clear_tool_uses_20250919" and edit["trigger"] == {"type": "input_tokens", "value": 12000}
    assert edit["clear_at_least"]["value"] == 6000


def test_context_editing_off_when_threshold_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, fake = claude_provider(monkeypatch, 0)
    assert not clears_tool_results(provider)
    provider.complete([UserMessage("x")], [])
    assert fake.kwargs["betas"] == [claude_module.FALLBACK_BETA] and fake.kwargs["context_management"] is anthropic.omit


def test_server_clearing_reaches_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    edit = {"type": "clear_tool_uses_20250919", "cleared_tool_uses": 4, "cleared_input_tokens": 9000}
    provider, _ = claude_provider(monkeypatch, 12000, [edit])
    assert provider.complete([UserMessage("x")], []).server_compaction == ServerCompaction(4, 9000)


def test_applied_edits_are_reported() -> None:
    final = BetaMessage.model_validate({
        "id": "m", "type": "message", "role": "assistant", "model": "m", "content": [], "stop_reason": "end_turn",
        "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        "context_management": {"applied_edits": [
            {"type": "clear_tool_uses_20250919", "cleared_tool_uses": 4, "cleared_input_tokens": 9000}]},
    })
    assert server_compaction(final) == ServerCompaction(4, 9000)


def test_no_applied_edits_means_no_report() -> None:
    final = BetaMessage.model_validate({
        "id": "m", "type": "message", "role": "assistant", "model": "m", "content": [], "stop_reason": "end_turn",
        "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
    })
    assert server_compaction(final) is None


class ServerClearing(ScriptedProvider):
    """像 Claude 一样由服务器清理：看到的历史必须一个字都没被客户端改过，并且第二轮报告清理了。"""

    clears_tool_results = True

    def complete(self, messages: Any, tools: Any, *, cancel: Any = None) -> LLMResponse:
        resp = super().complete(messages, tools, cancel=cancel)
        size = 50_000 if len(self.seen) > 1 else 10
        # 实测：服务器每次都重新清理完整的历史，同一批结果每轮都报告一次
        first, second = ServerCompaction(2, 9000), ServerCompaction(5, 20000)
        done = None if len(self.seen) < 2 else first if len(self.seen) < 5 else second
        usage = Usage(prompt_tokens=size)
        return LLMResponse(resp.content, resp.tool_calls, usage, resp.stop_reason, resp.native, done)


def test_agent_never_edits_history_when_server_clears(workspace: Path, settings: Settings) -> None:
    # 思考块的签名绑定它前面的全部内容，客户端改了旧的工具结果，接口返回 400
    (workspace / "big.txt").write_text("line of text here\n" * 2000)
    script = [*(LLMResponse(None, [call("read_file", path="big.txt")]) for _ in range(8)), LLMResponse("done")]
    llm = ServerClearing(script)
    custom = settings.model_copy(update={"context_compact_tokens": 1000, "repo_map_chars": 0})
    result = Agent(llm, workspace, custom, runner=NoSandboxRunner()).run("x")
    assert not any(isinstance(m, ToolResultMessage) and "output cleared" in m.content for m in llm.seen[-1])
    events = result.trace.of("context_compact")
    assert [(e["source"], e["cleared_results"], e["cleared_tokens"]) for e in events] == [
        ("server", 2, 9000), ("server", 3, 11000)]
    assert result.trace.summary()["compactions"] == 2 and result.trace.summary()["cleared_tokens"] == 20000
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage) and "output was cleared" in system.content
