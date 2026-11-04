"""OpenAI 兼容接口：DeepSeek、通义千问、小米 MiMo、Ollama、vLLM 都走这一个。"""

import threading
from collections.abc import Sequence
from typing import Any

import openai

from boxcode.config import Settings
from boxcode.llm.base import (
    AssistantMessage,
    LLMCancelled,
    LLMResponse,
    LLMUnavailable,
    Message,
    StopReason,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    Usage,
    UserMessage,
)

REQUEST_TIMEOUT_S = 120


def convert_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": t.name, "description": t.description,
                                              "parameters": t.parameters}} for t in tools]


def convert_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        match m:
            case SystemMessage():
                out.append({"role": "system", "content": m.content})
            case UserMessage():
                out.append({"role": "user", "content": m.content})
            case AssistantMessage():
                # native 是别的 Provider 的原始内容（例如 Claude 的思考块），不发出去
                msg: dict[str, Any] = {"role": "assistant", "content": m.content}
                if m.tool_calls:
                    msg["tool_calls"] = [
                        {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                        for c in m.tool_calls
                    ]
                out.append(msg)
            case ToolResultMessage():
                out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
    return out


def _stop_reason(finish_reason: str | None, refusal: str | None) -> StopReason:
    if refusal or finish_reason == "content_filter":
        return StopReason.REFUSAL
    if finish_reason == "length":
        return StopReason.MAX_TOKENS
    return StopReason.END


def _usage(u: Any) -> Usage:
    if u is None:
        return Usage()
    # OpenAI 放在 prompt_tokens_details.cached_tokens，DeepSeek 用自己的 prompt_cache_hit_tokens
    details = getattr(u, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) or getattr(u, "prompt_cache_hit_tokens", None) or 0
    return Usage(u.prompt_tokens or 0, u.completion_tokens or 0, int(cached))


class OpenAICompatProvider:
    def __init__(self, settings: Settings) -> None:
        api_key = settings.api_key.get_secret_value()
        if not api_key:
            raise LLMUnavailable("没有 API key：写进 ~/.boxcode/api_key，或者设置 BOXCODE_API_KEY"
                                 "（用 Ollama 时随便填一个，例如 ollama）")
        self.name = settings.model
        self._client = openai.OpenAI(base_url=settings.base_url, api_key=api_key, timeout=REQUEST_TIMEOUT_S)

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: threading.Event | None = None,
    ) -> LLMResponse:
        # 不用流式，请求发出去就没法中途放弃：只在发之前看一眼。按停止时 Agent 不等它返回
        if cancel is not None and cancel.is_set():
            raise LLMCancelled
        try:
            r = self._client.chat.completions.create(
                model=self.name,
                messages=convert_messages(messages),  # type: ignore[arg-type]
                tools=convert_tools(tools),  # type: ignore[arg-type]
            )
        except openai.OpenAIError as e:
            raise LLMUnavailable(str(e)) from e
        if not r.choices:
            raise LLMUnavailable("接口返回了空的 choices")
        choice = r.choices[0]
        msg = choice.message
        calls = [
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments)
            for c in (msg.tool_calls or [])
            if c.type == "function"
        ]
        return LLMResponse(content=msg.content, tool_calls=calls, usage=_usage(r.usage),
                           stop_reason=_stop_reason(choice.finish_reason, getattr(msg, "refusal", None)))
