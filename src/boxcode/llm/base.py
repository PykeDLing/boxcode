"""模型接口。

Agent 内部的对话历史、工具定义和模型回复都用这里的类型；每个 Provider 自己负责转成接口要的格式，
所以主循环不认识任何一家的格式，换模型只需新写一个 Provider。
"""

import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # 模型给的原始 JSON 字符串，解析和校验在工具里做


@dataclass(frozen=True)
class ToolSpec:
    """给模型看的工具定义：parameters 是 JSON Schema。"""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0  # 输入 token 总数，含命中缓存的部分
    completion_tokens: int = 0
    cached_tokens: int = 0  # 其中命中提示缓存的部分


@dataclass(frozen=True)
class ServerCompaction:
    """这一次请求里服务器清理掉的旧工具结果（见 Claude 的 context editing）。"""

    cleared_results: int
    cleared_tokens: int


class StopReason(StrEnum):
    END = "end"  # 正常结束：回答完了，或者要调用工具
    MAX_TOKENS = "max_tokens"  # 撞上输出上限：工具参数可能被截断
    REFUSAL = "refusal"  # 模型拒绝（Claude 的安全分类器、OpenAI 的 content_filter）


@dataclass(frozen=True)
class Native:
    """Provider 原样返回的回复内容，只有同一个 Provider 会读。

    例如 Claude 的思考块必须一个字节不差地回传，换成别的 Provider 时直接忽略。
    """

    provider: str
    payload: Any


@dataclass(frozen=True)
class SystemMessage:
    content: str


@dataclass(frozen=True)
class UserMessage:
    content: str


@dataclass(frozen=True)
class AssistantMessage:
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    native: Native | None = None


@dataclass(frozen=True)
class ToolResultMessage:
    tool_call_id: str
    content: str
    is_error: bool = False


Message = SystemMessage | UserMessage | AssistantMessage | ToolResultMessage


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = StopReason.END
    native: Native | None = None
    server_compaction: ServerCompaction | None = None

    @property
    def truncated(self) -> bool:
        """撞上输出上限时还带着工具调用：参数可能不完整，Agent 不执行这一轮的工具。"""
        return self.stop_reason is StopReason.MAX_TOKENS and bool(self.tool_calls)

    def to_message(self) -> AssistantMessage:
        """转成追加进对话历史的 assistant 消息。"""
        return AssistantMessage(self.content, tuple(self.tool_calls), self.native)


class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: threading.Event | None = None,
    ) -> LLMResponse:
        """cancel 被设置时尽快放弃这次请求（抛 LLMCancelled），不再为剩下的输出付钱。

        Agent 不靠这一点来及时停下：它在别的线程里调 complete，按停止后不等它返回。做不到中途放弃的
        Provider（例如不用流式的接口）可以忽略 cancel，请求会在后台自己结束，结果被丢掉。
        """
        ...


def clears_tool_results(llm: LLMProvider) -> bool:
    """Provider 自己在服务器端清理旧的工具结果时返回 True，主循环就不再动发出去的历史。

    不是 Protocol 的成员：只有 Claude 需要，其他 Provider 不用声明。
    """
    return getattr(llm, "clears_tool_results", False) is True


class LLMUnavailable(RuntimeError):
    """模型接口出错（超时、限流、鉴权失败）。"""


class LLMCancelled(Exception):
    """调用方取消了这次请求（界面上按了停止）。"""
