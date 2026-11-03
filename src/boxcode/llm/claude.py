"""Claude：走官方 anthropic SDK 的 Messages API。

Agent 内部的对话历史是 OpenAI 格式，这里在每次请求前转成 Claude 的格式：
- 第一条 system 消息 → 顶层 system；连续的 tool 消息 → 一条 user 消息里的多个 tool_result
- Claude 自己的 assistant 回复不转换：存在 `_anthropic_content` 里原样回传。思考块（thinking）
  必须原样带回，删掉或改动会让后面的请求出错，所以历史只追加、不修改
- 顶层 cache_control 自动缓存到最后一个内容块：Agent 每轮的前缀不变，越往后越省

请求用流式（工具参数里可能有整个文件），工具开启 eager_input_streaming，参数边生成边传回。
代价是服务器不再校验参数，所以：Agent 用 Pydantic 校验每个参数；撞上 max_tokens 的那一轮不执行工具；
SDK 解析不了的 JSON 会在流里抛 ValueError，这时整个请求重发。
"""

import json
from typing import Any, cast

import anthropic
from anthropic.types.beta import BetaOutputConfigParam

from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, LLMUnavailable, Message, ToolCall, Usage

MAX_TOKENS = 64000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
JSON_RETRIES = 2


def convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI 的 function 工具定义 → Claude 的工具定义。"""
    out = []
    for t in tools:
        fn = t["function"]
        out.append({
            "name": fn["name"],
            "description": fn["description"],
            "input_schema": fn["parameters"],
            "eager_input_streaming": True,
        })
    return out


def convert_messages(messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
    """OpenAI 格式的历史 → (system, Claude 的 messages)。"""
    system = ""
    out: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []

    def flush() -> None:
        # 同一轮的所有工具结果放进同一条 user 消息：拆开发会让模型以后不再并行调用工具
        if pending_results:
            out.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for m in messages:
        role = m["role"]
        if role == "system" and not out and not system:
            system = m["content"]
        elif role == "tool":
            result: dict[str, Any] = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            if m.get("_is_error"):
                result["is_error"] = True
            pending_results.append(result)
        elif role == "assistant":
            flush()
            out.append({"role": "assistant", "content": m.get("_anthropic_content") or _assistant_blocks(m)})
        else:  # user
            flush()
            out.append({"role": "user", "content": m["content"]})
    flush()
    return system, out


def _assistant_blocks(m: Message) -> list[dict[str, Any]]:
    """不是 Claude 生成的 assistant 消息（例如换过模型），按文字和工具调用重建。"""
    blocks: list[dict[str, Any]] = []
    if m.get("content"):
        blocks.append({"type": "text", "text": m["content"]})
    for c in m.get("tool_calls") or []:
        fn = c["function"]
        blocks.append({"type": "tool_use", "id": c["id"], "name": fn["name"],
                       "input": json.loads(fn["arguments"] or "{}")})
    return blocks


def strip_before_fallback(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """输出到一半被拒绝、由备用模型接着写时，回传前要去掉分界（最后一个 fallback 块）之前的
    思考块和工具调用；文字块照常保留。"""
    idx = max((i for i, b in enumerate(blocks) if b.get("type") == "fallback"), default=-1)
    if idx < 0:
        return blocks
    dropped = {"thinking", "redacted_thinking", "tool_use"}
    return [b for i, b in enumerate(blocks) if i > idx or b.get("type") not in dropped]


def parse_response(blocks: list[dict[str, Any]], stop_reason: str | None, usage: Usage) -> LLMResponse:
    blocks = strip_before_fallback(blocks)
    text = "\n".join(b["text"] for b in blocks if b.get("type") == "text" and b.get("text")) or None
    calls = [ToolCall(id=b["id"], name=b["name"], arguments=json.dumps(b.get("input") or {}, ensure_ascii=False))
             for b in blocks if b.get("type") == "tool_use"]
    return LLMResponse(
        content=text, tool_calls=calls, usage=usage, stop_reason=stop_reason,
        truncated=stop_reason == "max_tokens" and bool(calls), raw_content=blocks,
    )


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        self.name = settings.model
        self._model = settings.model
        self._effort = settings.effort
        # 不传 api_key：SDK 依次找 ANTHROPIC_API_KEY、ANTHROPIC_AUTH_TOKEN、`ant auth login` 的配置
        self._client = anthropic.Anthropic()

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        system, msgs = convert_messages(messages)
        for attempt in range(JSON_RETRIES + 1):
            try:
                with self._client.beta.messages.stream(
                    model=self._model,
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
                    final = stream.get_final_message()
                break
            except ValueError:
                # 流式工具参数不是合法 JSON，SDK 解析失败；这时拿不到 tool_use_id，只能整个重发
                if attempt == JSON_RETRIES:
                    raise LLMUnavailable("模型多次返回无法解析的工具参数") from None
            except anthropic.AuthenticationError as e:
                raise LLMUnavailable("Claude 鉴权失败：设置 ANTHROPIC_API_KEY，或运行 `ant auth login`") from e
            except anthropic.RateLimitError as e:
                raise LLMUnavailable(f"Claude 限流（SDK 已自动重试）：{e.message}") from e
            except anthropic.APIStatusError as e:
                raise LLMUnavailable(f"Claude 接口错误 {e.status_code}：{e.message}") from e
            except anthropic.APIConnectionError as e:
                raise LLMUnavailable(f"连不上 Claude：{e}") from e

        u = final.usage
        cached = (u.cache_read_input_tokens or 0) + (u.cache_creation_input_tokens or 0)
        usage = Usage(prompt_tokens=u.input_tokens + cached, completion_tokens=u.output_tokens,
                      cached_tokens=u.cache_read_input_tokens or 0)
        return parse_response([b.to_dict() for b in final.content], final.stop_reason, usage)
