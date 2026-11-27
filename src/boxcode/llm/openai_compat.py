"""OpenAI 兼容接口：DeepSeek、通义千问、小米 MiMo、Ollama、vLLM 都走这一个。

默认用流式输出（Settings.stream）：回复一块一块地到，每收到一块看一眼调用方有没有取消，取消了就断开连接，
服务器不再往下生成。不用流式时请求发出去就只能等它整个返回。
"""

import json
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import openai
from openai.types.chat import ChatCompletionChunk

from boxcode.config import Settings
from boxcode.llm.base import (
    AssistantMessage,
    IncompleteReply,
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

# 流没有收到 finish_reason 就结束时，同一个请求最多重发这么多次。本机模型实测（Ollama）：模型输出的工具调用
# 格式不完整，Ollama 解析不了，不发结束标记就把流关了，状态码还是 200；144 次运行里遇到 4 次，重跑同一道题都没有再遇到。
# 这时回复还没有交给主循环，什么都没执行，重发是安全的。和 Claude 那边工具参数解析不了时的做法一样（JSON_RETRIES）
STREAM_RETRIES = 2


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
                # 没有正文也没有工具调用的回复（例如输出上限全被思考用完了）：按接口定义这时 content 必填，
                # 发 null 过去 Ollama 返回 400，整次运行就断在这里
                content = m.content if m.content is not None or m.tool_calls else ""
                msg: dict[str, Any] = {"role": "assistant", "content": content}
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


@dataclass
class _PartialCall:
    """流式回复里的一个工具调用：id、名字、参数都是一段一段到的。"""

    id: str = ""
    name: str = ""
    arguments: str = ""


def read_stream(chunks: Iterable[ChatCompletionChunk], cancel: threading.Event | None) -> LLMResponse:
    """把流式的数据块拼成一条回复。

    每收到一块看一眼 cancel：按了停止就抛 LLMCancelled，调用的地方随即关掉连接。两块之间不看：
    模型长时间不出字（例如还在思考）时，要等到下一块到了才断开。
    """
    text: list[str] = []
    refusal: list[str] = []
    calls: dict[int, _PartialCall] = {}  # 同一个调用的各段靠 index 对上，id 只在第一段里有
    finish_reason: str | None = None
    usage: Any = None
    answered = False
    for chunk in chunks:
        if cancel is not None and cancel.is_set():
            raise LLMCancelled
        if chunk.usage is not None:  # 带了 include_usage 时在最后一块里，那一块的 choices 是空的
            usage = chunk.usage
        if not chunk.choices:
            continue
        answered = True
        choice = chunk.choices[0]
        finish_reason = choice.finish_reason or finish_reason
        delta = choice.delta
        text.append(delta.content or "")
        refusal.append(delta.refusal or "")
        for part in delta.tool_calls or []:
            partial = calls.setdefault(part.index, _PartialCall())
            partial.id += part.id or ""
            if part.function is not None:
                partial.name += part.function.name or ""
                partial.arguments += part.function.arguments or ""
    if not answered:
        raise LLMUnavailable("接口返回了空的 choices")
    if finish_reason is None:
        # 连接中途断了，或者接口没按约定收尾：工具参数可能只到了一半，不能当成完整的回复去执行
        raise IncompleteReply("回复没有收完（没有 finish_reason）：连接可能中途断了；"
                              "接口的流式输出不完整的话，设置 BOXCODE_STREAM=false")
    return LLMResponse(
        content="".join(text) or None,
        tool_calls=[ToolCall(id=c.id, name=c.name, arguments=c.arguments) for _, c in sorted(calls.items())],
        usage=_usage(usage), stop_reason=_stop_reason(finish_reason, "".join(refusal) or None),
    )


class OpenAICompatProvider:
    def __init__(self, settings: Settings) -> None:
        api_key = settings.api_key.get_secret_value()
        if not api_key:
            raise LLMUnavailable("没有 API key：写进 ~/.boxcode/api_key，或者设置 BOXCODE_API_KEY"
                                 "（用 Ollama 时随便填一个，例如 ollama）")
        self.name = settings.model
        self._stream = settings.stream
        # thinking 不是 OpenAI 的标准参数，SDK 里只能放在 extra_body；default 时不带，不认识它的接口不受影响
        self._extra_body = {"thinking": {"type": "disabled"}} if settings.thinking == "disabled" else None
        # 0 表示不带 max_tokens。用 max_tokens 而不是新的 max_completion_tokens：各家兼容接口都认前一个
        self._max_tokens = settings.max_output_tokens or openai.omit
        self._client = openai.OpenAI(base_url=settings.base_url, api_key=api_key, timeout=settings.request_timeout_s)

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: threading.Event | None = None,
    ) -> LLMResponse:
        if cancel is not None and cancel.is_set():
            raise LLMCancelled
        try:
            if self._stream:
                return self._complete_stream(messages, tools, cancel)
            return self._complete_whole(messages, tools)
        except openai.OpenAIError as e:  # 流读到一半连接断开、超时，SDK 也包成它的异常
            raise LLMUnavailable(str(e)) from e
        except json.JSONDecodeError as e:  # 流里有一条数据不是 JSON，SDK 原样抛出来
            raise LLMUnavailable(f"接口返回的流式数据解析不了：{e}") from e

    def _complete_stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], cancel: threading.Event | None,
    ) -> LLMResponse:
        attempt = 0
        while True:
            if cancel is not None and cancel.is_set():
                raise LLMCancelled
            # 消息和工具是普通的 dict，对不上 SDK 的 TypedDict：带了 stream=True 以后 mypy 报在整个调用上
            stream: openai.Stream[ChatCompletionChunk] = self._client.chat.completions.create(  # type: ignore[call-overload]
                model=self.name,
                messages=convert_messages(messages),
                # 空的工具列表会被拒绝（Claude 的兼容接口返回 400）：没有工具就不带
                tools=convert_tools(tools) or openai.omit,
                max_tokens=self._max_tokens,
                extra_body=self._extra_body,
                stream=True,
                stream_options={"include_usage": True},  # 不带的话流式回复里没有 token 用量
            )
            try:
                with stream:  # 取消或出错时关掉连接：服务器不再往下生成
                    return replace(read_stream(stream, cancel), retries=attempt)
            except IncompleteReply:
                if attempt == STREAM_RETRIES:
                    raise
                attempt += 1

    def _complete_whole(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMResponse:
        # 不用流式，请求发出去就没法中途放弃：只在发之前看一眼。按停止时 Agent 不等它返回
        r = self._client.chat.completions.create(
            model=self.name,
            messages=convert_messages(messages),  # type: ignore[arg-type]
            tools=convert_tools(tools) or openai.omit,  # type: ignore[arg-type]
            max_tokens=self._max_tokens,
            extra_body=self._extra_body,
        )
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
