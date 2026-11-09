"""上下文压缩：对话太长时，把旧的工具结果换成一行说明，调用本身和模型的结论都留着。

用在 OpenAI 兼容接口上。Claude 不能用这个：思考块的签名绑定它前面的全部内容，改旧的工具结果会让接口返回 400，
Claude 由服务器清理（见 llm/claude.py），这里的阈值是 0。

对话历史（state.messages）始终完整、只追加；发给模型的是 view() 生成的一份副本。

清理是一批一批做的，不是每轮重新算：提示缓存按前缀匹配，每轮改动旧消息等于每轮都不命中。所以估算超过阈值时
一次清到阈值的一半，清过的永远保持清理后的样子，下一次超过阈值之前前缀都不变。

位置用消息在历史里的下标，工具名按结果在这一轮里的顺序对应，都不用 tool_call_id：
有的本地模型每次都发一样的 id（例如 call_0）。
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace

from boxcode.llm.base import AssistantMessage, Message, ToolCall, ToolResultMessage

# 消息的角色、分隔符之类的开销，粗略估计
MESSAGE_OVERHEAD_TOKENS = 4
# 最近这么多轮工具调用的结果不清理：模型多半正要用
KEEP_RECENT_TURNS = 2
# 比这短的结果清理了也省不了多少
MIN_CLEAR_CHARS = 600
# 一次省不到这么多就不动：清理一次，缓存就要从被改的位置重建
MIN_SAVED_TOKENS = 1000
# run_command 的结果清理后留下退出码和结尾（测试的汇总、报错常在最后）
TAIL_LINES = 3
KEPT_LINE_CHARS = 150


def estimate_tokens(text: str) -> int:
    """没有分词器时的粗略估算：英文和代码约 3.5 字符一个 token，中文约 1.5 字符一个。"""
    non_ascii = (len(text.encode("utf-8", "replace")) - len(text)) // 2
    ascii_chars = max(len(text) - non_ascii, 0)
    return ascii_chars * 2 // 7 + non_ascii * 2 // 3


def message_tokens(m: Message) -> int:
    if isinstance(m, AssistantMessage):
        calls = sum(estimate_tokens(c.name) + estimate_tokens(c.arguments) for c in m.tool_calls)
        return MESSAGE_OVERHEAD_TOKENS + estimate_tokens(m.content or "") + calls
    return MESSAGE_OVERHEAD_TOKENS + estimate_tokens(m.content)


def placeholder(call: ToolCall | None, text: str) -> str:
    """换掉工具结果的那段话，给模型看的。"""
    name = call.name if call is not None else "tool"
    note = (f"[{name} output cleared to save context ({len(text)} characters). The call above shows what was run; "
            "run it again only if you still need the output.]")
    if name != "run_command":
        return note
    # 第一行是退出码，最后几行常是测试汇总或报错；stdout、stderr 的分隔行没有信息
    lines = [line for line in text.split("\n") if line.strip() and not line.startswith("--- std")]
    kept = dict.fromkeys(line[:KEPT_LINE_CHARS] for line in [*lines[:1], *lines[-TAIL_LINES:]])
    return note + "\nFirst and last lines of the output:\n" + "\n".join(kept)


@dataclass(frozen=True)
class Compaction:
    """一次清理的结果，写进轨迹。token 数是估算值。"""

    before_tokens: int
    after_tokens: int
    cleared_results: int
    cleared_chars: int


class ContextCompactor:
    """threshold_tokens 为 0 表示不压缩。"""

    def __init__(self, threshold_tokens: int) -> None:
        self.threshold = threshold_tokens
        self.target = threshold_tokens // 2
        self._placeholders: dict[int, str] = {}  # 历史里的下标 → 换上去的文字，只增不改
        self._anchor: tuple[int, int] | None = None  # 上一次请求的真实输入 token 数，和当时的消息条数
        self._next_trigger = threshold_tokens  # 上下文超过这个数才清理

    def observe(self, prompt_tokens: int, message_count: int) -> None:
        """记下接口报的真实 token 数（含系统提示和工具定义）。不报用量的接口传 0，之后全靠估算。"""
        self._anchor = (prompt_tokens, message_count) if prompt_tokens > 0 else None

    def view(self, messages: Sequence[Message]) -> list[Message]:
        """发给模型的那一份：清理过的工具结果换成说明，其余原样。"""
        return [replace(m, content=self._placeholders[i]) if isinstance(m, ToolResultMessage)
                and i in self._placeholders else m for i, m in enumerate(messages)]

    def context_tokens(self, messages: Sequence[Message]) -> int:
        """这一轮要发的上下文有多大：上次的真实用量加上之后新增消息的估算，没有真实用量就全部估算。"""
        if self._anchor is not None:
            tokens, count = self._anchor
            return tokens + sum(message_tokens(m) for m in messages[count:])
        return sum(message_tokens(m) for m in self.view(messages))

    def _candidates(self, messages: Sequence[Message]) -> Iterator[tuple[int, ToolResultMessage, str]]:
        """能清理的结果，从旧到新。"""
        turns = [i for i, m in enumerate(messages) if isinstance(m, AssistantMessage) and m.tool_calls]
        if len(turns) <= KEEP_RECENT_TURNS:
            return
        protected_from = turns[-KEEP_RECENT_TURNS]
        calls: tuple[ToolCall, ...] = ()
        position = 0  # 这一轮的第几个结果：主循环按调用的顺序追加结果，同一轮里 id 重复时也对得上
        for i, m in enumerate(messages[:protected_from]):
            if isinstance(m, AssistantMessage):
                calls, position = m.tool_calls, 0
            elif isinstance(m, ToolResultMessage):
                call = calls[position] if position < len(calls) else None
                position += 1
                if i not in self._placeholders and len(m.content) >= MIN_CLEAR_CHARS:
                    text = placeholder(call, m.content)
                    if len(text) < len(m.content):  # 刚过下限的 run_command 结果，说明可能比原文还长
                        yield i, m, text

    def compact(self, messages: Sequence[Message]) -> Compaction | None:
        """超过阈值就清理一批，返回这次清理的情况；没到阈值或者省不了多少时什么都不改，返回 None。"""
        if self.threshold <= 0:
            return None
        before = self.context_tokens(messages)
        if before <= self._next_trigger:
            return None
        chosen: dict[int, str] = {}
        tokens = before
        chars = 0
        for i, m, text in self._candidates(messages):
            if tokens <= self.target:
                break
            chosen[i] = text
            tokens -= estimate_tokens(m.content) - estimate_tokens(text)
            chars += len(m.content) - len(text)
        if before - tokens < max(MIN_SAVED_TOKENS, self.threshold // 20):
            return None
        self._placeholders.update(chosen)
        self._anchor = None  # 上次的真实用量已经不对了，这一轮的回复回来之前按估算算
        # 最近几轮的结果不清理，它们本身就可能占满额度（实测阈值 9000 时每一轮都在清理、每次只清一个，缓存轮轮失效）。
        # 所以清理之后还在阈值以上时，要再涨够一个间隔才清理下一批
        self._next_trigger = max(self.threshold, tokens + self.target)
        return Compaction(before, tokens, len(chosen), chars)
