"""文件工具。在 Agent 进程里执行（不经过沙盒），所以路径一律限制在工作区内。"""

from pydantic import BaseModel, Field

from boxcode.tools.base import Risk, Tool, ToolContext, ToolError, ToolResult, resolve_in_workspace, truncate

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}


class ReadFile(Tool):
    name = "read_file"
    description = "Read a text file in the workspace. Output has 1-based line numbers."
    risk = Risk.READ

    class Params(BaseModel):
        path: str = Field(description="Path relative to the workspace root")
        offset: int = Field(default=1, ge=1, description="First line to read")
        limit: int = Field(default=400, ge=1, le=2000, description="Max number of lines")

    def run(self, ctx: ToolContext, params: Params) -> ToolResult:
        p = resolve_in_workspace(ctx.workspace, params.path)
        if not p.is_file():
            raise ToolError(f"不是文件：{params.path}")
        lines = p.read_text(errors="replace").splitlines()
        chunk = lines[params.offset - 1 : params.offset - 1 + params.limit]
        body = "\n".join(f"{i:>5}\t{line}" for i, line in enumerate(chunk, params.offset))
        more = len(lines) - (params.offset - 1 + len(chunk))
        tail = f"\n... 还有 {more} 行，用 offset 继续读" if more > 0 else ""
        return ToolResult(truncate(body, ctx.settings.max_tool_output) + tail)


class ListDir(Tool):
    name = "list_dir"
    description = "List files under a directory in the workspace (recursive, skips .git, node_modules, venvs)."
    risk = Risk.READ

    class Params(BaseModel):
        path: str = Field(default=".", description="Directory relative to the workspace root")
        max_entries: int = Field(default=300, ge=1, le=2000)

    def run(self, ctx: ToolContext, params: Params) -> ToolResult:
        root = resolve_in_workspace(ctx.workspace, params.path)
        if not root.is_dir():
            raise ToolError(f"不是目录：{params.path}")
        out: list[str] = []
        for p in sorted(root.rglob("*")):
            if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
                continue
            out.append(str(p.relative_to(ctx.workspace)) + ("/" if p.is_dir() else ""))
            if len(out) >= params.max_entries:
                out.append(f"... 超过 {params.max_entries} 项，已截断")
                break
        return ToolResult("\n".join(out) or "(空目录)")


class WriteFile(Tool):
    name = "write_file"
    description = "Create or overwrite a file in the workspace with the given content."
    risk = Risk.WRITE

    class Params(BaseModel):
        path: str
        content: str

    def run(self, ctx: ToolContext, params: Params) -> ToolResult:
        p = resolve_in_workspace(ctx.workspace, params.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(params.content)
        return ToolResult(f"已写入 {params.path}（{len(params.content)} 个字符）")


class EditFile(Tool):
    name = "edit_file"
    description = (
        "Replace an exact snippet in a file. old_string must appear exactly once; "
        "include enough surrounding lines to make it unique."
    )
    risk = Risk.WRITE

    class Params(BaseModel):
        path: str
        old_string: str = Field(min_length=1)
        new_string: str

    def run(self, ctx: ToolContext, params: Params) -> ToolResult:
        p = resolve_in_workspace(ctx.workspace, params.path)
        if not p.is_file():
            raise ToolError(f"不是文件：{params.path}")
        text = p.read_text()
        n = text.count(params.old_string)
        if n != 1:
            raise ToolError(f"old_string 在文件里出现了 {n} 次，必须恰好 1 次")
        p.write_text(text.replace(params.old_string, params.new_string, 1))
        return ToolResult(f"已修改 {params.path}")
