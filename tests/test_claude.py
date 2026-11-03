"""Claude 的格式转换。不发请求，只测转换和回复解析。"""

import json
from pathlib import Path

from boxcode.agent import Agent, Status
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, Usage
from boxcode.llm.claude import convert_messages, convert_tools, parse_response, strip_before_fallback
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.sandbox import NoSandboxRunner
from boxcode.tools import default_tools

THINKING = {"type": "thinking", "thinking": "", "signature": "sig-abc"}
TOOL_USE = {"type": "tool_use", "id": "toolu_1", "name": "list_dir", "input": {"path": "."}}


def test_tools_converted_with_eager_streaming() -> None:
    tools = convert_tools([t.schema() for t in default_tools()])
    edit = next(t for t in tools if t["name"] == "edit_file")
    assert edit["input_schema"]["required"] == ["path", "old_string", "new_string"]
    assert all(t["eager_input_streaming"] for t in tools)


def test_parallel_tool_results_merged_into_one_user_message() -> None:
    raw = [THINKING, TOOL_USE, {**TOOL_USE, "id": "toolu_2"}]
    system, msgs = convert_messages([
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": None, "_anthropic_content": raw},
        {"role": "tool", "tool_call_id": "toolu_1", "content": "a", "_is_error": False},
        {"role": "tool", "tool_call_id": "toolu_2", "content": "boom", "_is_error": True},
        {"role": "user", "content": "check failed"},
    ])
    assert system == "SYS"
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "user"]
    assert msgs[1]["content"] is raw  # 原样回传，思考块一个不少
    results = msgs[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["toolu_1", "toolu_2"]
    assert "is_error" not in results[0] and results[1]["is_error"] is True


def test_assistant_from_other_provider_rebuilt() -> None:
    _, msgs = convert_messages([
        {"role": "user", "content": "x"},
        {"role": "assistant", "content": "looking", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "grep", "arguments": '{"pattern": "a"}'}}]},
    ])
    assert msgs[1]["content"] == [
        {"type": "text", "text": "looking"},
        {"type": "tool_use", "id": "c1", "name": "grep", "input": {"pattern": "a"}},
    ]


def test_parse_response_keeps_raw_blocks() -> None:
    blocks = [THINKING, {"type": "text", "text": "Let me look."}, TOOL_USE]
    r = parse_response(blocks, "tool_use", Usage(10, 5, 8))
    assert r.content == "Let me look."
    assert r.tool_calls[0].name == "list_dir" and json.loads(r.tool_calls[0].arguments) == {"path": "."}
    assert not r.truncated
    assert r.to_message()["_anthropic_content"] == blocks


def test_max_tokens_with_tool_call_is_truncated() -> None:
    assert parse_response([TOOL_USE], "max_tokens", Usage()).truncated


def test_blocks_before_fallback_dropped() -> None:
    blocks = [THINKING, {"type": "text", "text": "partial"}, TOOL_USE,
              {"type": "fallback"}, {"type": "text", "text": "rest"}, {**TOOL_USE, "id": "toolu_9"}]
    kept = strip_before_fallback(blocks)
    assert [b["type"] for b in kept] == ["text", "fallback", "text", "tool_use"]
    assert parse_response(blocks, "tool_use", Usage()).tool_calls[0].id == "toolu_9"


def test_truncated_tool_calls_not_executed(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([
        LLMResponse(None, [call("write_file", path="big.txt", content="half")], truncated=True),
        LLMResponse("ok"),
    ])
    Agent(llm, workspace, settings, runner=NoSandboxRunner()).run("write")
    assert not (workspace / "big.txt").exists()
    tool_msg = llm.seen[1][-1]
    assert tool_msg["role"] == "tool" and tool_msg["_is_error"] is True and "max_tokens" in tool_msg["content"]


def test_refusal_stops_without_running_tools(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse(None, [call("write_file", path="x", content="y")], stop_reason="refusal")])
    result = Agent(llm, workspace, settings, runner=NoSandboxRunner()).run("x")
    assert result.status is Status.REFUSED
    assert not (workspace / "x").exists()
