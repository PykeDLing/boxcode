"""Claude：走官方 anthropic SDK 的 Messages API。

每次请求前把 Agent 的对话历史转成 Claude 的格式：
- 第一条 SystemMessage → 顶层 system；连续的工具结果 → 一条 user 消息里的多个 tool_result
- Claude 自己的 assistant 回复不转换：原始内容块存在 AssistantMessage.native 里原样回传。思考块（thinking）
  必须原样带回，删掉或改动会让后面的请求出错，所以历史只追加、不修改
- 顶层 cache_control 自动缓存到最后一个内容块：Agent 每轮的前缀不变，越往后越省

请求用流式（工具参数里可能有整个文件），工具开启 eager_input_streaming，参数边生成边传回。
代价是服务器不再校验参数，所以：工具用 Pydantic 校验每个参数；撞上 max_tokens 的那一轮不执行工具；
SDK 解析不了的 JSON 会在流里抛 ValueError，这时拿不到 tool_use_id，只能整个请求重发。

流式还有一个好处：每收到一个事件都能看一眼 cancel，按了停止就断开连接（见 read_stream）。
"""

import json
import threading
from collections.abc import Iterator, Sequence
from typing import Any, Protocol, cast

import anthropic
from anthropic.types.beta import BetaMessage, BetaOutputConfigParam

from boxcode.config import Settings
from boxcode.llm.base import (
    AssistantMessage,
    LLMCancelled,
    LLMResponse,
    LLMUnavailable,
    Message,
    Native,
    StopReason,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    Usage,
)

PROVIDER = "anthropic"
MAX_TOKENS = 64000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
JSON_RETRIES = 2

Block = dict[str, Any]

# 输出被截断的几种停止原因：工具参数可能不完整
_TRUNCATED = {"max_tokens", "model_context_window_exceeded"}


def convert_tools(tools: Sequence[ToolSpec]) -> list[Block]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.parameters, "eager_input_streaming": True}
        for t in tools
    ]


def convert_messages(messages: Sequence[Message]) -> tuple[str, list[Block]]:
    """对话历史 → (system, Claude 的 messages)。"""
    system = ""
    out: list[Block] = []
    pending_results: list[Block] = []

    def flush() -> None:
        # 同一轮的所有工具结果放进同一条 user 消息：拆开发会让模型以后不再并行调用工具
        if pending_results:
            out.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for m in messages:
        match m:
            case SystemMessage() if not out and not system:
                system = m.content
            case ToolResultMessage():
                result: Block = {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
                if m.is_error:
                    result["is_error"] = True
                pending_results.append(result)
            case AssistantMessage():
                flush()
                out.append({"role": "assistant", "content": _assistant_blocks(m)})
            case _:  # UserMessage，以及不在开头的 SystemMessage（Agent 不会这样发，当作用户消息）
                flush()
                out.append({"role": "user", "content": m.content})
    flush()
    return system, out


def _assistant_blocks(m: AssistantMessage) -> list[Block]:
    if m.native is not None and m.native.provider == PROVIDER:
        return cast(list[Block], m.native.payload)
    # 不是 Claude 生成的回复（例如中途换过模型）：按文字和工具调用重建
    blocks: list[Block] = []
    if m.content:
        blocks.append({"type": "text", "text": m.content})
    blocks.extend({"type": "tool_use", "id": c.id, "name": c.name, "input": _loads_object(c.arguments)}
                  for c in m.tool_calls)
    return blocks


def _loads_object(arguments: str) -> dict[str, Any]:
    # 别的模型给的参数可能不是合法 JSON（那次调用已经作为错误回给了模型），这里只要能发出去
    try:
        value = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def strip_before_fallback(blocks: list[Block]) -> list[Block]:
    """输出到一半被拒绝、由备用模型接着写时，回传前要去掉分界（最后一个 fallback 块）之前的
    思考块和工具调用；文字块照常保留。"""
    idx = max((i for i, b in enumerate(blocks) if b.get("type") == "fallback"), default=-1)
    if idx < 0:
        return blocks
    dropped = {"thinking", "redacted_thinking", "tool_use"}
    return [b for i, b in enumerate(blocks) if i > idx or b.get("type") not in dropped]


def _stop_reason(raw: str | None) -> StopReason:
    if raw == "refusal":
        return StopReason.REFUSAL
    if raw in _TRUNCATED:
        return StopReason.MAX_TOKENS
    return StopReason.END


def parse_response(blocks: list[Block], stop_reason: str | None, usage: Usage) -> LLMResponse:
    blocks = strip_before_fallback(blocks)
    text = "\n".join(b["text"] for b in blocks if b.get("type") == "text" and b.get("text")) or None
    calls = [ToolCall(id=b["id"], name=b["name"], arguments=json.dumps(b.get("input") or {}, ensure_ascii=False))
             for b in blocks if b.get("type") == "tool_use"]
    return LLMResponse(content=text, tool_calls=calls, usage=usage, stop_reason=_stop_reason(stop_reason),
                       native=Native(PROVIDER, blocks))


class _Stream(Protocol):
    def __iter__(self) -> Iterator[object]: ...

    def get_final_message(self) -> BetaMessage: ...


def read_stream(stream: _Stream, cancel: threading.Event | None) -> BetaMessage:
    """一个事件一个事件地读，每读一个看一眼 cancel：按了停止就抛 LLMCancelled，
    外面的 with 随即关掉连接，服务器停止生成，剩下的输出不再计费。
    生成过程中事件很密（思考、文字、工具参数的增量），长时间没有输出时服务器也会发 ping。"""
    for _ in stream:
        if cancel is not None and cancel.is_set():
            raise LLMCancelled
    return stream.get_final_message()


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        self.name = settings.model
        self._effort = settings.effort
        # 不传 api_key：SDK 依次找 ANTHROPIC_API_KEY、ANTHROPIC_AUTH_TOKEN、`ant auth login` 的配置
        self._client = anthropic.Anthropic()

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: threading.Event | None = None,
    ) -> LLMResponse:
        system, msgs = convert_messages(messages)
        for attempt in range(JSON_RETRIES + 1):
            if cancel is not None and cancel.is_set():
                raise LLMCancelled
            try:
                with self._client.beta.messages.stream(
                    model=self.name,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    messages=msgs,  # type: ignore[arg-type]
                    tools=convert_tools(tools),  # type: ignore[arg-type]
                    output_config=cast(BetaOutputConfigParam, {"effort": self._effort}),
                    cache_control={"type": "ephemeral"},
                    # 被安全分类器拒绝时，服务器按拒绝类别自动换备用模型重跑
                    betas=[FALLBACK_BETA],
                    fallbacks="default",
                ) as stream:
                    final = read_stream(stream, cancel)
                break
            except anthropic.AuthenticationError as e:
                raise LLMUnavailable("Claude 鉴权失败：设置 ANTHROPIC_API_KEY，或运行 `ant auth login`") from e
            except anthropic.RateLimitError as e:
                raise LLMUnavailable(f"Claude 限流（SDK 已自动重试）：{e.message}") from e
            except anthropic.APIStatusError as e:
                raise LLMUnavailable(f"Claude 接口错误 {e.status_code}：{e.message}") from e
            except anthropic.APIConnectionError as e:
                raise LLMUnavailable(f"连不上 Claude：{e}") from e
            except ValueError:
                # 流式工具参数不是合法 JSON，SDK 解析失败；这时拿不到 tool_use_id，只能整个重发
                if attempt == JSON_RETRIES:
                    raise LLMUnavailable("模型多次返回无法解析的工具参数") from None

        u = final.usage
        cache_read = u.cache_read_input_tokens or 0
        cache_write = u.cache_creation_input_tokens or 0
        usage = Usage(prompt_tokens=u.input_tokens + cache_read + cache_write, completion_tokens=u.output_tokens,
                      cached_tokens=cache_read)
        return parse_response([b.to_dict() for b in final.content], final.stop_reason, usage)
