"""判分时用 `-p boxcode.evals.pytest_report` 加载的 pytest 插件，在测试进程里：

- 装上导入钩子：测试导入 editable 里的模块时，换成被测进程里的模块的代理（见 remote.py）。
  被测代码不在这个进程里运行，改不了这里的数据、换不掉 pytest 的内部函数
- 把收集到的测试和每个测试的结果写进 BOXCODE_REPORT_FD 这个文件描述符：它指向一个已经删掉的临时文件，
  没有路径，被测进程（以及测试里起的子进程）都拿不到

判分看这份报告，而不是只看退出码：被测代码在导入时 `os._exit(0)`，退出码是 0，但报告里那些测试没有通过。
"""

import json
import os
from typing import Any

import pytest

from boxcode.evals.remote import REPORT_FD_ENV, install_from_env

_collected: list[str] = []
# 每个测试的结果：call 阶段通过记 "passed"；任何阶段没通过记 "<阶段>:<结果>"，例如 "setup:skipped"
_outcomes: dict[str, str] = {}

_report_fd: int | None = None
if fd := os.environ.get(REPORT_FD_ENV):
    _report_fd = int(fd)
    os.set_inheritable(_report_fd, False)  # 测试里起的子进程（可能在跑被测代码）不继承它
install_from_env()


def pytest_collection_finish(session: pytest.Session) -> None:
    _collected[:] = [item.nodeid for item in session.items]


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.outcome != "passed":
        _outcomes[report.nodeid] = f"{report.when}:{report.outcome}"
    elif report.when == "call":
        _outcomes.setdefault(report.nodeid, "passed")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _report_fd is None:
        return
    data: dict[str, Any] = {"exitstatus": int(exitstatus), "collected": _collected, "outcomes": _outcomes}
    view = memoryview(json.dumps(data).encode())
    while view:
        view = view[os.write(_report_fd, view):]
