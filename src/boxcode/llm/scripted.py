"""按剧本回答的假模型：测试和评测框架自测用，不需要 API key，结果可复现。"""

import json
from typing import Any

from boxcode.llm.base import LLMResponse, Message, ToolCall


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=f"call_{name}_{id(arguments)}", name=name, arguments=json.dumps(arguments))


class ScriptedProvider:
    name = "scripted"

    def __init__(self, script: list[LLMResponse]) -> None:
        self._script = list(script)
        self.seen: list[list[Message]] = []  # 每次被调用时看到的对话，测试里用来断言

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        self.seen.append([dict(m) for m in messages])
        if not self._script:
            return LLMResponse(content="(剧本结束)")
        return self._script.pop(0)
