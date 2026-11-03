from boxcode.config import Settings
from boxcode.llm.base import LLMProvider, LLMUnavailable


def make_provider(settings: Settings) -> LLMProvider:
    """按 BOXCODE_PROVIDER 选模型接口。"""
    if settings.provider == "anthropic":
        from boxcode.llm.claude import AnthropicProvider

        return AnthropicProvider(settings)
    if settings.provider == "openai":
        from boxcode.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(settings)
    raise LLMUnavailable(f"不认识的 BOXCODE_PROVIDER：{settings.provider}（可选 openai、anthropic）")
