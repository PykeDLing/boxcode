"""Claude 的格式转换。不发请求，只测转换、回复解析和读流。"""

import json
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from anthropic.types.beta import BetaMessage

from boxcode.llm.base import (
    AssistantMessage,
    LLMCancelled,
    Native,
    StopReason,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from boxcode.llm.claude import (
    PROVIDER,
    convert_messages,
    convert_tools,
    parse_response,
    read_stream,
    strip_before_fallback,
)
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
