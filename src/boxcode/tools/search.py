import re

from pydantic import BaseModel, Field

from boxcode.tools.base import Risk, Tool, ToolContext, ToolError, ToolResult, resolve_in_workspace
from boxcode.tools.fs import SKIP_DIRS


class Grep(Tool):
    name = "grep"
    description = "Search file contents in the workspace with a Python regular expression."
    risk = Risk.READ

    class Params(BaseModel):
        pattern: str
        path: str = Field(default=".", description="Directory or file to search")
        max_results: int = Field(default=100, ge=1, le=1000)

    def run(self, ctx: ToolContext, params: Params) -> ToolResult:
        try:
            rx = re.compile(params.pattern)
        except re.error as e:
            raise ToolError(f"正则写错了：{e}") from e
        root = resolve_in_workspace(ctx.workspace, params.path)
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        hits: list[str] = []
        for f in files:
            if not f.is_file() or any(part in SKIP_DIRS for part in f.parts):
                continue
            try:
                lines = f.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue  # 二进制文件
            for i, line in enumerate(lines, 1):
                if rx.search(line):
                    hits.append(f"{f.relative_to(ctx.workspace)}:{i}: {line.strip()[:200]}")
                    if len(hits) >= params.max_results:
                        return ToolResult("\n".join(hits) + "\n... 结果太多，已截断")
        return ToolResult("\n".join(hits) or "没有匹配")
