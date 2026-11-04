import re
import time

from pydantic import Field

from boxcode.tools.base import Risk, Tool, ToolContext, ToolError, ToolParams, ToolResult, resolve_in_workspace
from boxcode.tools.fs import MAX_FILE_BYTES, display, is_binary, read_workspace_bytes, rel, split_lines, walk_workspace

# 每行匹配结果最多显示这么多字符（压缩过的 JS 一行就有几百 KB）
MAX_LINE_CHARS = 200
# 整个搜索最多花这么久：grep 在 Agent 进程里执行，没有命令那样的超时。
# 只在两行之间检查，单独一行上的灾难性回溯（例如 ^(a|a)*$）仍然打断不了，这是 Python re 的限制
TIME_BUDGET_S = 30


class GrepParams(ToolParams):
    pattern: str = Field(description="Python regular expression")
    path: str = Field(default=".", description="Directory or file to search, relative to the workspace root")
    max_results: int = Field(default=100, ge=1, le=1000)


class Grep(Tool[GrepParams]):
    name = "grep"
    description = "Search file contents in the workspace with a Python regular expression."
    risk = Risk.READ
    Params = GrepParams

    def run(self, ctx: ToolContext, params: GrepParams) -> ToolResult:
        try:
            rx = re.compile(params.pattern)
        except re.error as e:
            raise ToolError(f"正则写错了：{e}") from e
        root = resolve_in_workspace(ctx.workspace, params.path)
        files = [root] if root.is_file() else walk_workspace(ctx.workspace, root)
        deadline = time.monotonic() + TIME_BUDGET_S
        hits: list[str] = []
        skipped = 0
        for f in files:
            if ctx.cancel.is_set() or time.monotonic() > deadline:
                return ToolResult("\n".join([*hits, f"... 搜索超过 {TIME_BUDGET_S} 秒或被停止，结果不完整"]))
            try:
                # 符号链接一律不跟：指向工作区内的，目标文件本身会被搜到
                if f.is_symlink() or not f.is_file():
                    continue
                if f.stat().st_size > MAX_FILE_BYTES:
                    skipped += 1
                    continue
                data = read_workspace_bytes(ctx.workspace, rel(ctx, f))
                if is_binary(data):
                    continue
                lines = split_lines(data.decode())
            except (UnicodeDecodeError, OSError, ToolError):
                continue  # 不是 UTF-8 文本、读不了、路径太长，或者在读的时候被换成了链接
            for i, line in enumerate(lines, 1):
                if rx.search(line):
                    if len(hits) == params.max_results:
                        return ToolResult("\n".join(hits) + "\n... 结果太多，已截断；把 pattern 或 path 写得更具体")
                    hits.append(f"{display(rel(ctx, f))}:{i}: {line.strip()[:MAX_LINE_CHARS]}")
        note = f"\n（跳过了 {skipped} 个超过 {MAX_FILE_BYTES // 1024 // 1024} MB 的文件）" if skipped else ""
        return ToolResult(("\n".join(hits) or "没有匹配") + note)
