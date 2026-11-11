"""OpenAI 兼容接口的格式转换和回复解析。不发请求：把 SDK 的 create 换成返回固定回复的函数。"""

from typing import Any

import pytest
from openai.types.chat import ChatCompletion

from boxcode.config import Settings, Thinking
from boxcode.llm.base import (
    AssistantMessage,
    LLMUnavailable,
    Native,
    StopReason,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    UserMessage,
)
from boxcode.llm.openai_compat import OpenAICompatProvider, convert_messages, convert_tools


def test_messages_converted_and_native_content_dropped() -> None:
    out = convert_messages([
        SystemMessage("SYS"), UserMessage("task"),
        AssistantMessage(None, (ToolCall("c1", "grep", '{"pattern":"a"}'),), native=Native("anthropic", ["thinking"])),
        ToolResultMessage("c1", "hit", is_error=True),
    ])
    assert out == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "grep", "arguments": '{"pattern":"a"}'}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "hit"},
    ]
    assert convert_tools([ToolSpec("t", "d", {"type": "object"})]) == [
        {"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}]


def completion(finish_reason: str, usage: dict[str, Any] | None = None, **message: Any) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": finish_reason,
                     "message": {"role": "assistant", "content": None, **message}}],
        "usage": usage,
    })


def provider(monkeypatch: pytest.MonkeyPatch, reply: ChatCompletion) -> OpenAICompatProvider:
    p = OpenAICompatProvider(Settings(api_key="k"))
    monkeypatch.setattr(p._client.chat.completions, "create", lambda **_: reply)
    return p


def test_tool_calls_and_cached_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = completion("tool_calls", {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
                                      "prompt_tokens_details": {"cached_tokens": 64}},
                       tool_calls=[{"id": "c1", "type": "function", "function": {"name": "grep", "arguments": "{}"}}])
    r = provider(monkeypatch, reply).complete([UserMessage("x")], [])
    assert r.tool_calls == [ToolCall("c1", "grep", "{}")] and r.stop_reason is StopReason.END
    assert (r.usage.prompt_tokens, r.usage.completion_tokens, r.usage.cached_tokens) == (100, 7, 64)


def test_deepseek_cache_field(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = completion("stop", {"prompt_tokens": 50, "completion_tokens": 1, "total_tokens": 51,
                                "prompt_cache_hit_tokens": 32}, content="hi")
    r = provider(monkeypatch, reply).complete([UserMessage("x")], [])
    assert r.content == "hi" and r.usage.cached_tokens == 32


def test_length_means_truncated_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # 以前只有 Claude 会把撞上输出上限的工具调用拦下来，OpenAI 兼容接口照样执行半截参数
    reply = completion("length", tool_calls=[
        {"id": "c1", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "a", "con'}}])
    r = provider(monkeypatch, reply).complete([UserMessage("x")], [])
    assert r.stop_reason is StopReason.MAX_TOKENS and r.truncated


def test_content_filter_is_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    r = provider(monkeypatch, completion("content_filter")).complete([UserMessage("x")], [])
    assert r.stop_reason is StopReason.REFUSAL


def test_thinking_disabled_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    # 小米 MiMo 默认开思考，不回传 reasoning_content 会报 400：能在请求里关掉。默认不带这个参数
    sent: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> ChatCompletion:
        sent.append(kwargs)
        return completion("stop", content="ok")

    options: tuple[Thinking, ...] = ("default", "disabled")
    for thinking in options:
        p = OpenAICompatProvider(Settings(api_key="k", thinking=thinking))
        monkeypatch.setattr(p._client.chat.completions, "create", create)
        p.complete([UserMessage("x")], [])
    assert [k["extra_body"] for k in sent] == [None, {"thinking": {"type": "disabled"}}]


def test_missing_key_and_empty_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(LLMUnavailable, match="BOXCODE_API_KEY"):
        OpenAICompatProvider(Settings())
    empty = completion("stop").model_copy(update={"choices": []})
    with pytest.raises(LLMUnavailable, match="choices"):
        provider(monkeypatch, empty).complete([UserMessage("x")], [])
