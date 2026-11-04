"""按剧本回答的假模型：测试和评测框架自测用，不需要 API key，结果可复现。"""

import itertools
import json
from collections.abc import Sequence
from typing import Any

from boxcode.llm.base import LLMResponse, Message, ToolCall, ToolSpec

_ids = itertools.count(1)


def call(name: str, **arguments: Any) -> ToolCall:
    # id 必须唯一：同一轮里两个调用 id 相同，转成 Claude 的格式就是非法请求
    return ToolCall(id=f"call_{next(_ids)}_{name}", name=name, arguments=json.dumps(arguments))


class ScriptedProvider:
    name = "scripted"

    def __init__(self, script: Sequence[LLMResponse]) -> None:
        self._script = list(script)
        self.seen: list[list[Message]] = []  # 每次被调用时看到的对话，测试里用来断言
        self.tools: list[ToolSpec] = []

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMResponse:
        self.seen.append(list(messages))
        self.tools = list(tools)
        if not self._script:
            return LLMResponse(content="(剧本结束)")
        return self._script.pop(0)
