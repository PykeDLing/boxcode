"""OpenAI 兼容接口：DeepSeek、通义千问、小米 MiMo、Ollama、vLLM 都走这一个。"""

from typing import Any

import openai

from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, LLMUnavailable, Message, ToolCall, Usage


class OpenAICompatProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.api_key:
            raise LLMUnavailable("没有设置 BOXCODE_API_KEY（用 Ollama 时随便填一个，例如 ollama）")
        self.name = settings.model
        self._model = settings.model
        self._client = openai.OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=120)

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        # 以下划线开头的键是给别的 Provider 的（例如 Claude 的原始内容块），不发出去
        clean = [{k: v for k, v in m.items() if not k.startswith("_")} for m in messages]
        try:
            r = self._client.chat.completions.create(
                model=self._model,
                messages=clean,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
            )
        except openai.OpenAIError as e:
            raise LLMUnavailable(str(e)) from e
        msg = r.choices[0].message
        calls = [
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments)
            for c in (msg.tool_calls or [])
            if c.type == "function"
        ]
        usage = Usage(r.usage.prompt_tokens, r.usage.completion_tokens) if r.usage else Usage()
        return LLMResponse(content=msg.content, tool_calls=calls, usage=usage)
