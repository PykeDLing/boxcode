"""所有可调参数，都能用环境变量覆盖。"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


DEFAULT_MODELS = {"openai": "deepseek-chat", "anthropic": "claude-opus-5-5"}


def _default_model() -> str:
    return _env("BOXCODE_MODEL", DEFAULT_MODELS.get(_env("BOXCODE_PROVIDER", "openai"), ""))


@dataclass(frozen=True)
class Settings:
    # openai：任何 OpenAI 兼容接口（DeepSeek、通义千问、小米 MiMo、本机 Ollama、vLLM）
    # anthropic：Claude，走官方 anthropic SDK
    provider: str = field(default_factory=lambda: _env("BOXCODE_PROVIDER", "openai"))
    model: str = field(default_factory=_default_model)
    # 下面两项只给 openai 用；anthropic 的凭证由 SDK 自己找（ANTHROPIC_API_KEY 或 `ant auth login`）
    base_url: str = field(default_factory=lambda: _env("BOXCODE_BASE_URL", "https://api.deepseek.com"))
    api_key: str = field(default_factory=lambda: _env("BOXCODE_API_KEY", ""))
    # Claude 的思考深度：low / medium / high / xhigh / max
    effort: str = field(default_factory=lambda: _env("BOXCODE_EFFORT", "high"))
    # 执行轨迹存在这里，不写进工作区
    home: Path = field(default_factory=lambda: Path(_env("BOXCODE_HOME", str(Path.home() / ".boxcode"))))
    max_turns: int = field(default_factory=lambda: int(_env("BOXCODE_MAX_TURNS", "30")))
    # 跑完后自检失败，最多再给模型几次修正机会
    max_fix_rounds: int = field(default_factory=lambda: int(_env("BOXCODE_MAX_FIX_ROUNDS", "2")))
    command_timeout_s: int = field(default_factory=lambda: int(_env("BOXCODE_COMMAND_TIMEOUT", "120")))
    # 工具结果回给模型前截断到这么多字符，防止上下文被一次输出撑爆
    max_tool_output: int = field(default_factory=lambda: int(_env("BOXCODE_MAX_TOOL_OUTPUT", "12000")))

    @property
    def runs_dir(self) -> Path:
        return self.home / "runs"
