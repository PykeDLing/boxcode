"""所有可调参数。

`Settings()` 只有默认值，不读环境变量（测试里构造出来的配置不受本机环境影响）；
命令行和桌面界面用 `Settings.from_env()`，每一项都能用 BOXCODE_* 环境变量覆盖，写错了在启动时就报出来。

API key 建议放在 `~/.boxcode/api_key` 文件里，而不是环境变量：沙盒里的命令能读到同一个用户下任何进程启动时的
环境变量（sysctl KERN_PROCARGS2，Seatbelt 挡不住），包括 BoxCode 自己和你的 shell；~/.boxcode 在沙盒里读不到。
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

Provider = Literal["openai", "anthropic"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]
Thinking = Literal["default", "disabled"]

DEFAULT_MODELS: dict[str, str] = {"openai": "deepseek-chat", "anthropic": "claude-opus-5-5"}
# 没设置 BOXCODE_API_KEY 时，从 BoxCode 数据目录下的这个文件读
API_KEY_FILE = "api_key"

# 字段 → 环境变量
ENV_VARS: dict[str, str] = {
    "provider": "BOXCODE_PROVIDER",
    "model": "BOXCODE_MODEL",
    "base_url": "BOXCODE_BASE_URL",
    "api_key": "BOXCODE_API_KEY",
    "effort": "BOXCODE_EFFORT",
    "thinking": "BOXCODE_THINKING",
    "home": "BOXCODE_HOME",
    "max_turns": "BOXCODE_MAX_TURNS",
    "max_fix_rounds": "BOXCODE_MAX_FIX_ROUNDS",
    "command_timeout_s": "BOXCODE_COMMAND_TIMEOUT",
    "max_tool_output": "BOXCODE_MAX_TOOL_OUTPUT",
    "context_compact_tokens": "BOXCODE_CONTEXT_COMPACT_TOKENS",
    "repo_map_chars": "BOXCODE_REPO_MAP_CHARS",
    "planning": "BOXCODE_PLANNING",
}


class ConfigError(ValueError):
    """环境变量的值不合法。消息里写的是环境变量名，直接给用户看。"""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # openai：任何 OpenAI 兼容接口（DeepSeek、通义千问、小米 MiMo、本机 Ollama、vLLM）
    # anthropic：Claude，走官方 anthropic SDK
    provider: Provider = "openai"
    # 不填就按 provider 取 DEFAULT_MODELS 里的默认
    model: str = ""
    # 下面两项只给 openai 用；anthropic 的凭证由 SDK 自己找（ANTHROPIC_API_KEY 或 `ant auth login`）
    base_url: str = "https://api.deepseek.com"
    api_key: SecretStr = SecretStr("")  # SecretStr：打印配置、写进日志时不会露出 key
    # Claude 的思考深度
    effort: Effort = "high"
    # OpenAI 兼容接口的深度思考：default 不带这个参数，由接口自己决定；disabled 在请求里关掉。
    # 小米 MiMo 默认开着思考，并且要求把 reasoning_content 原样传回，BoxCode 没有回传，不关会报 400
    thinking: Thinking = "default"
    # 执行轨迹存在这里，不写进工作区
    home: Path = Field(default_factory=lambda: Path.home() / ".boxcode")
    max_turns: int = Field(default=30, ge=1)
    # 跑完后自检失败，最多再给模型几次修正机会
    max_fix_rounds: int = Field(default=2, ge=0)
    command_timeout_s: int = Field(default=120, ge=1)
    # 工具结果回给模型前截断到这么多字符，防止上下文被一次输出撑爆
    max_tool_output: int = Field(default=12000, ge=1000)
    # 对话估算超过这么多 token 时清理旧的工具结果，0 表示不压缩（对比实验用）
    context_compact_tokens: int = Field(default=40000, ge=0)
    # 第一条消息里代码库地图的长度上限，0 表示不生成
    repo_map_chars: int = Field(default=8000, ge=0)
    # 是否给模型 update_plan 工具
    planning: bool = True

    @model_validator(mode="before")
    @classmethod
    def _default_model(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("model"):
            return {**data, "model": DEFAULT_MODELS.get(str(data.get("provider", "openai")), "")}
        return data

    @property
    def runs_dir(self) -> Path:
        return self.home / "runs"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        values: dict[str, Any] = {name: env[var] for name, var in ENV_VARS.items() if env.get(var)}
        if "api_key" not in values:
            key_file = Path(values.get("home") or Path.home() / ".boxcode") / API_KEY_FILE
            if key_file.is_file():
                values["api_key"] = key_file.read_text(encoding="utf-8").strip()
        try:
            return cls.model_validate(values)
        except ValidationError as e:
            problems = []
            for err in e.errors():
                name = str(err["loc"][0]) if err["loc"] else ""
                var = ENV_VARS.get(name, name)
                shown = "***" if name == "api_key" else repr(values.get(name))
                problems.append(f"{var}={shown}：{err['msg']}")
            raise ConfigError("配置不对：" + "；".join(problems)) from None
