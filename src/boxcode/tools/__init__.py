from typing import Any

from boxcode.tools.base import Risk, Target, Tool, ToolContext, ToolError, ToolParams, ToolResult
from boxcode.tools.fs import EditFile, ListDir, ReadFile, WriteFile
from boxcode.tools.plan import UpdatePlan
from boxcode.tools.search import Grep
from boxcode.tools.shell import RunCommand


def default_tools(planning: bool = True) -> list[Tool[Any]]:
    tools: list[Tool[Any]] = [ReadFile(), ListDir(), Grep(), WriteFile(), EditFile(), RunCommand()]
    return [*tools, UpdatePlan()] if planning else tools


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
    "UpdatePlan",
    "WriteFile",
    "default_tools",
]
