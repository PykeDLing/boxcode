from boxcode.config import Settings
from boxcode.llm.base import LLMProvider


def make_provider(settings: Settings) -> LLMProvider:
    """按 BOXCODE_PROVIDER 选模型接口。SDK 只在用到时导入。"""
    match settings.provider:
        case "anthropic":
            from boxcode.llm.claude import AnthropicProvider

            return AnthropicProvider(settings)
        case "openai":
            from boxcode.llm.openai_compat import OpenAICompatProvider

            return OpenAICompatProvider(settings)
