import sys
from pathlib import Path

import pytest

from boxcode.config import Settings


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws.resolve()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(api_key="test", home=tmp_path / "boxcode-home")


macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt 只在 macOS 上")
