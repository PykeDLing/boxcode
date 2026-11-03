"""模型接口。消息直接用 OpenAI Chat Completions 的格式，换模型只需新写一个 Provider。"""

from dataclasses import dataclass, field
from typing import Any, Protocol

Message = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # 模型给的原始 JSON 字符串，解析和校验在 Agent 里做


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0  # 输入 token 总数，含命中缓存的部分
    completion_tokens: int = 0
    cached_tokens: int = 0  # 其中命中提示缓存的部分


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    # "refusal"：模型拒绝回答（Claude 的安全分类器）；Agent 据此结束，不执行这一轮的工具
    stop_reason: str | None = None
    # 输出撞上 max_tokens：工具参数可能被截断，Agent 不执行这一轮的工具
    truncated: bool = False
    # Claude 原样返回的内容块（含思考块），下一轮必须原样回传，见 llm/anthropic.py
    raw_content: list[dict[str, Any]] | None = None

    def to_message(self) -> Message:
        """转成追加进对话历史的 assistant 消息。以下划线开头的键只给对应的 Provider 看。"""
        msg: Message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in self.tool_calls
            ]
        if self.raw_content is not None:
            msg["_anthropic_content"] = self.raw_content
        return msg


class LLMProvider(Protocol):
    name: str

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse: ...


class LLMUnavailable(RuntimeError):
    """模型接口出错（超时、限流、鉴权失败）。"""
