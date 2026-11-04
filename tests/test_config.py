"""配置：Settings() 不读环境变量，from_env() 读并且在启动时就把写错的值报出来。"""

from pathlib import Path

import pytest

from boxcode.config import ConfigError, Settings


def test_defaults_ignore_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # 测试里构造的配置不能被开发者机器上的 BOXCODE_* 影响
    monkeypatch.setenv("BOXCODE_MAX_TURNS", "3")
    monkeypatch.setenv("BOXCODE_PROVIDER", "anthropic")
    s = Settings()
    assert s.max_turns == 30 and s.provider == "openai" and s.model == "deepseek-chat"


def test_from_env_parses_and_derives_model() -> None:
    s = Settings.from_env({"BOXCODE_PROVIDER": "anthropic", "BOXCODE_MAX_TURNS": "5", "BOXCODE_HOME": "/x/y",
                           "BOXCODE_EFFORT": "max", "BOXCODE_MODEL": ""})
    assert s.provider == "anthropic" and s.model == "claude-opus-5-5"  # 空值当作没设置
    assert s.max_turns == 5 and s.home == Path("/x/y") and s.runs_dir == Path("/x/y/runs") and s.effort == "max"
    assert Settings.from_env({"BOXCODE_MODEL": "qwen-max"}).model == "qwen-max"
    assert Settings(provider="anthropic").model == "claude-opus-5-5"


@pytest.mark.parametrize(("env", "var"), [
    ({"BOXCODE_MAX_TURNS": "lots"}, "BOXCODE_MAX_TURNS"),
    ({"BOXCODE_MAX_TURNS": "0"}, "BOXCODE_MAX_TURNS"),
    ({"BOXCODE_PROVIDER": "gemini"}, "BOXCODE_PROVIDER"),
    ({"BOXCODE_EFFORT": "ultra"}, "BOXCODE_EFFORT"),
])
def test_bad_values_name_the_variable(env: dict[str, str], var: str) -> None:
    with pytest.raises(ConfigError, match=var):
        Settings.from_env(env)


def test_api_key_never_shown() -> None:
    s = Settings.from_env({"BOXCODE_API_KEY": "sk-secret-123"})
    assert s.api_key.get_secret_value() == "sk-secret-123"
    assert "sk-secret-123" not in repr(s) and "sk-secret-123" not in str(s.model_dump())


def test_settings_are_immutable() -> None:
    s = Settings()
    with pytest.raises(ValueError, match="frozen"):
        s.max_turns = 1  # type: ignore[misc]
    assert s.model_copy(update={"max_turns": 1}).max_turns == 1


def test_api_key_read_from_file_when_not_in_env(tmp_path: Path) -> None:
    # 环境变量里的 key 沙盒里的命令读得到（KERN_PROCARGS2），~/.boxcode 里的文件读不到
    (tmp_path / "api_key").write_text("sk-from-file\n")
    s = Settings.from_env({"BOXCODE_HOME": str(tmp_path)})
    assert s.api_key.get_secret_value() == "sk-from-file"
    assert Settings.from_env({"BOXCODE_HOME": str(tmp_path), "BOXCODE_API_KEY": "sk-env"}).api_key.get_secret_value() \
        == "sk-env"
    assert Settings.from_env({"BOXCODE_HOME": str(tmp_path / "none")}).api_key.get_secret_value() == ""
