import time

import regex
from pydantic import Field

from boxcode.tools.base import Risk, Tool, ToolContext, ToolError, ToolParams, ToolResult, resolve_in_workspace
from boxcode.tools.fs import MAX_FILE_BYTES, display, is_binary, read_workspace_bytes, rel, split_lines, walk_workspace

# 每行匹配结果最多显示这么多字符（压缩过的 JS 一行就有几百 KB）
MAX_LINE_CHARS = 200
# 整个搜索最多花这么久：grep 在 Agent 进程里执行，没有命令那样的超时
TIME_BUDGET_S = 30
# 单独一行最多匹配这么久，超过了这一行按没匹配处理、在结果里注明。正常的正则一行只要几微秒，
# 超过的多半是灾难性回溯（例如 ^(a|a)*$）。用 regex 库而不是 re：re 一旦开始匹配就停不下来，
# 还一直占着 GIL，桌面界面连“停止”都点不动；regex 能设超时，concurrent=True 匹配时释放 GIL
LINE_TIMEOUT_S = 1.0
# 结果末尾最多列出这么多个匹配超时的位置
MAX_TIMEOUT_REPORTS = 5


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
            rx = regex.compile(params.pattern)
        except regex.error as e:
            raise ToolError(f"正则写错了：{e}") from e
        root = resolve_in_workspace(ctx.workspace, params.path)
        files = [root] if root.is_file() else walk_workspace(ctx.workspace, root)
        deadline = time.monotonic() + TIME_BUDGET_S
        hits: list[str] = []
        slow: list[str] = []  # 匹配超时、按没匹配处理的行
        skipped = 0

        def finish(ending: str | None = None) -> ToolResult:
            """ending：结果不完整时的说明（被截断、超时、被停止）。"""
            out = [*hits, ending] if ending else (hits or ["没有匹配"])
            if slow:
                shown = "、".join(slow[:MAX_TIMEOUT_REPORTS]) + ("……" if len(slow) > MAX_TIMEOUT_REPORTS else "")
                out.append(f"（{len(slow)} 行匹配超过 {LINE_TIMEOUT_S:g} 秒，按没匹配处理，"
                           f"多半是正则回溯太多，换个写法：{shown}）")
            if skipped:
                out.append(f"（跳过了 {skipped} 个超过 {MAX_FILE_BYTES // 1024 // 1024} MB 的文件）")
            return ToolResult("\n".join(out))

        stopped = f"... 搜索超过 {TIME_BUDGET_S} 秒或被停止，结果不完整"
        for f in files:
            if ctx.cancel.is_set() or time.monotonic() > deadline:
                return finish(stopped)
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
                remaining = deadline - time.monotonic()
                if ctx.cancel.is_set() or remaining <= 0:
                    return finish(stopped)
                try:
                    matched = rx.search(line, concurrent=True, timeout=min(LINE_TIMEOUT_S, remaining))
                except TimeoutError:
                    if time.monotonic() < deadline:  # 是这一行太慢，不是整个搜索的时间用完了
                        slow.append(f"{display(rel(ctx, f))}:{i}")
                    continue
                if matched:
                    if len(hits) == params.max_results:
                        return finish("... 结果太多，已截断；把 pattern 或 path 写得更具体")
                    hits.append(f"{display(rel(ctx, f))}:{i}: {line.strip()[:MAX_LINE_CHARS]}")
        return finish()
