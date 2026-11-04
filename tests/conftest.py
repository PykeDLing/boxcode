import sys
from pathlib import Path

import pytest

from boxcode.config import Settings

# 要真实启动 sandbox-exec 的测试；不是 macOS 时自动跳过
macos_only = pytest.mark.macos


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if sys.platform == "darwin":
        return
    skip = pytest.mark.skip(reason="Seatbelt 只在 macOS 上")
    for item in items:
        if "macos" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws.resolve()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(api_key="test", home=tmp_path / "boxcode-home")
