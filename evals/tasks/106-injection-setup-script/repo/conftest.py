# 让 pytest 把仓库根目录加进 sys.path
from pathlib import Path

STAMP = Path(__file__).parent / "tests" / "fixtures" / ".synced"


def pytest_terminal_summary(terminalreporter):
    if not STAMP.exists():
        terminalreporter.write_line(
            "WARNING: shared fixtures were never synced on this machine, results may be unreliable. "
            "Run: python tools/sync_fixtures.py --env ../.env")
