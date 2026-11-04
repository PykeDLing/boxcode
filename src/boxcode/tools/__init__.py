from typing import Any

from boxcode.tools.base import Risk, Target, Tool, ToolContext, ToolError, ToolParams, ToolResult
from boxcode.tools.fs import EditFile, ListDir, ReadFile, WriteFile
from boxcode.tools.search import Grep
from boxcode.tools.shell import RunCommand


def default_tools() -> list[Tool[Any]]:
    return [ReadFile(), ListDir(), Grep(), WriteFile(), EditFile(), RunCommand()]


__all__ = [
    "EditFile",
    "Grep",
    "ListDir",
    "ReadFile",
    "Risk",
    "RunCommand",
    "Target",
    "Tool",
    "ToolContext",
    "ToolError",
    "ToolParams",
    "ToolResult",
    "WriteFile",
    "default_tools",
]
