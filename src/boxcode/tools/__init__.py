from boxcode.tools.base import Risk, Target, Tool, ToolContext, ToolError, ToolResult
from boxcode.tools.fs import EditFile, ListDir, ReadFile, WriteFile
from boxcode.tools.search import Grep
from boxcode.tools.shell import RunCommand


def default_tools() -> list[Tool]:
    return [ReadFile(), ListDir(), Grep(), WriteFile(), EditFile(), RunCommand()]


__all__ = [
    "Risk", "Target", "Tool", "ToolContext", "ToolError", "ToolResult",
    "EditFile", "Grep", "ListDir", "ReadFile", "RunCommand", "WriteFile", "default_tools",
]
