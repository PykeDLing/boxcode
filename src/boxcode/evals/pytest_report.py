"""判分时用 `-p boxcode.evals.pytest_report` 加载的 pytest 插件：把收集到的测试和每个测试的结果
写进环境变量 BOXCODE_REPORT 指向的 JSON 文件。

判分看这份报告，而不是只看退出码：Agent 写的代码在导入时 `os._exit(0)`，退出码是 0，但报告不会生成。
它和被测代码在同一个进程里，专门针对它伪造报告的代码仍然防不住；完全防住要把测试和被测代码放进不同的进程。
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

_collected: list[str] = []
# 每个测试的结果：call 阶段通过记 "passed"；任何阶段没通过记 "<阶段>:<结果>"，例如 "setup:skipped"
_outcomes: dict[str, str] = {}


def pytest_collection_finish(session: pytest.Session) -> None:
    _collected[:] = [item.nodeid for item in session.items]


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.outcome != "passed":
        _outcomes[report.nodeid] = f"{report.when}:{report.outcome}"
    elif report.when == "call":
        _outcomes.setdefault(report.nodeid, "passed")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    path = os.environ.get("BOXCODE_REPORT")
    if not path:
        return
    data: dict[str, Any] = {"exitstatus": int(exitstatus), "collected": _collected, "outcomes": _outcomes}
    Path(path).write_text(json.dumps(data), encoding="utf-8")
