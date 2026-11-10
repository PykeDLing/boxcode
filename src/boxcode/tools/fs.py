"""文件工具。在 Agent 进程里执行（不经过沙盒），所以路径一律限制在工作区内，读写一律经过 open_in_workspace。"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import BinaryIO

from pydantic import Field

from boxcode.tools.base import (
    Risk,
    Target,
    Tool,
    ToolContext,
    ToolError,
    ToolParams,
    ToolResult,
    in_workspace,
    open_in_workspace,
    resolve_in_workspace,
)

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
# 比这大的文件不整个读进来：多半是数据、日志或者打包产物
MAX_FILE_BYTES = 10 * 1024 * 1024
# 开头这么多字节里有 NUL 就当二进制文件
BINARY_SNIFF_BYTES = 8192


def _entries(d: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(d) as it:
            return sorted(it, key=lambda e: e.name)
    except OSError:  # 没有权限、遍历途中被删掉
        return []


def walk_workspace(
    workspace: Path, root: Path, skip_dir: Callable[[str], bool] = lambda _: False,
    stop: Callable[[], bool] = lambda: False,
) -> Iterator[Path]:
    """按目录树的顺序（先目录本身，再它下面的东西）逐个给出 root 下的文件和目录。

    不进入 SKIP_DIRS（APFS 默认不区分大小写，.GIT 也算），不跟随目录链接，跳过指向工作区外的符号链接：
    沙盒里的命令可以建一个指向 ~/.ssh/id_rsa 的链接，文件工具不在沙盒里，跟着链接就读出来了。
    边遍历边给出，调用方够数了就能停，不用先把整个仓库走一遍。skip_dir 按目录名再跳过一些。
    stop 每看一项之前调用一次，返回 True 就结束：被跳过的项调用方看不到，靠调用方自己计数拦不住一堆指向外面的链接。
    """
    stack = [iter(_entries(root))]
    while stack:
        if stop():
            return
        entry = next(stack[-1], None)
        if entry is None:
            stack.pop()
            continue
        p = Path(entry.path)
        if entry.is_symlink() and not in_workspace(workspace, p):
            continue
        is_dir = entry.is_dir(follow_symlinks=False)
        if is_dir and (entry.name.casefold() in SKIP_DIRS or skip_dir(entry.name)):
            continue
        yield p
        if is_dir:
            stack.append(iter(_entries(p)))


def _check_size(f: BinaryIO) -> None:
    size = os.fstat(f.fileno()).st_size
    if size > MAX_FILE_BYTES:
        raise ToolError(f"文件太大（{size} 字节），先用 grep 找到要看的位置")


def read_workspace_bytes(workspace: Path, path: str) -> bytes:
    with open_in_workspace(workspace, path) as f:
        _check_size(f)
        return f.read()


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:BINARY_SNIFF_BYTES]


def split_lines(text: str) -> list[str]:
    """只按 \n 分行（去掉行尾的 \r）：str.splitlines() 还会在 \x0c、\x1c、\u2028 这些字符处断行，
    行号就和编辑器、pytest、sed 对不上了。"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [line.removesuffix("\r") for line in lines]


def display(rel: str) -> str:
    """文件名里有换行、控制字符、U+2028、双向文字控制符时转义显示：不然叫 "a\nINJECTED" 的文件看起来是两项。"""
    return repr(rel) if not rel.isprintable() else rel


def _to_crlf(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\n", "\r\n")


def rel(ctx: ToolContext, p: Path) -> str:
    return p.relative_to(ctx.workspace).as_posix()


class ReadFileParams(ToolParams):
    path: str = Field(description="Path relative to the workspace root")
    offset: int = Field(default=1, ge=1, description="First line to read (1-based)")
    limit: int = Field(default=400, ge=1, le=2000, description="Max number of lines")


class ReadFile(Tool[ReadFileParams]):
    name = "read_file"
    description = "Read a text file in the workspace. Output has 1-based line numbers."
    risk = Risk.READ
    Params = ReadFileParams

    def run(self, ctx: ToolContext, params: ReadFileParams) -> ToolResult:
        data = read_workspace_bytes(ctx.workspace, params.path)
        if is_binary(data):
            raise ToolError(f"{params.path} 是二进制文件，不能按文本读")
        lines = split_lines(data.decode(errors="replace"))
        start = params.offset - 1
        chunk = lines[start : start + params.limit]
        if not chunk and lines:
            raise ToolError(f"offset 超出文件末尾：文件只有 {len(lines)} 行")
        body = "\n".join(f"{i:>5}\t{line}" for i, line in enumerate(chunk, params.offset))
        more = len(lines) - (start + len(chunk))
        tail = f"\n... 还有 {more} 行，用 offset={start + len(chunk) + 1} 继续读" if more > 0 else ""
        return ToolResult((body or "(空文件)") + tail)


class ListDirParams(ToolParams):
    path: str = Field(default=".", description="Directory relative to the workspace root")
    max_entries: int = Field(default=300, ge=1, le=2000)


class ListDir(Tool[ListDirParams]):
    name = "list_dir"
    description = "List files under a directory in the workspace (recursive, skips .git, node_modules, venvs)."
    risk = Risk.READ
    Params = ListDirParams

    def run(self, ctx: ToolContext, params: ListDirParams) -> ToolResult:
        root = resolve_in_workspace(ctx.workspace, params.path)
        if not root.is_dir():
            raise ToolError(f"不是目录：{params.path}")
        out: list[str] = []
        for p in walk_workspace(ctx.workspace, root):
            if len(out) >= params.max_entries:
                out.append(f"... 超过 {params.max_entries} 项，已截断；换一个更小的目录")
                break
            try:
                is_dir = p.is_dir()
            except OSError:  # 路径太长（超过 1024 字节）之类：这一项跳过，别让整个列表失败
                continue
            out.append(display(rel(ctx, p)) + ("/" if is_dir else ""))
        return ToolResult("\n".join(out) or "(空目录)")


class WriteFileParams(ToolParams):
    path: str = Field(description="Path relative to the workspace root")
    content: str = Field(description="Full new content of the file")


class WriteFile(Tool[WriteFileParams]):
    name = "write_file"
    description = "Create or overwrite a file in the workspace with the given content."
    risk = Risk.WRITE
    Params = WriteFileParams

    def target(self, ctx: ToolContext, params: WriteFileParams) -> Target:
        return Target(paths=(resolve_in_workspace(ctx.workspace, params.path),))

    def run(self, ctx: ToolContext, params: WriteFileParams) -> ToolResult:
        # 内容按 UTF-8 原样写入，不做换行符转换；目录不存在就建
        with open_in_workspace(ctx.workspace, params.path, write=True, create=True) as f:
            f.truncate(0)
            f.write(params.content.encode())
        return ToolResult(f"已写入 {params.path}（{len(params.content)} 个字符）")


class EditFileParams(ToolParams):
    path: str = Field(description="Path relative to the workspace root")
    old_string: str = Field(min_length=1, description="Exact text to replace, including indentation")
    new_string: str = Field(description="Replacement text")


class EditFile(Tool[EditFileParams]):
    name = "edit_file"
    description = (
        "Replace an exact snippet in a file. old_string must appear exactly once; "
        "include enough surrounding lines to make it unique."
    )
    risk = Risk.WRITE
    Params = EditFileParams

    def target(self, ctx: ToolContext, params: EditFileParams) -> Target:
        return Target(paths=(resolve_in_workspace(ctx.workspace, params.path),))

    def run(self, ctx: ToolContext, params: EditFileParams) -> ToolResult:
        with open_in_workspace(ctx.workspace, params.path, write=True) as f:
            _check_size(f)
            try:
                # 按字节解码、不转换换行符：Windows 换行（CRLF）的文件改完还是 CRLF
                text = f.read().decode()
            except UnicodeDecodeError as e:
                raise ToolError(f"{params.path} 不是 UTF-8 文本，不能用 edit_file 改") from e
            new_text = self._replace(text, params)
            f.seek(0)
            f.truncate()
            f.write(new_text.encode())
        return ToolResult(f"已修改 {params.path}")

    @staticmethod
    def _replace(text: str, params: EditFileParams) -> str:
        old, new = params.old_string, params.new_string
        if old == new:
            raise ToolError("old_string 和 new_string 一样，没有要改的")
        if "\r\n" in text and "\n" not in text.replace("\r\n", ""):
            # 整个文件都是 CRLF：模型给的片段多半是 \n 换行，两边都换成 CRLF，改完不会混进 LF
            old, new = _to_crlf(old), _to_crlf(new)
        n = text.count(old)
        if n == 0 and "\r\n" in text and "\n" in old:
            # 换行符混用的文件：先按原样找，找不到再按 CRLF 找一次
            n = text.count(crlf := _to_crlf(old))
            if n:
                old, new = crlf, _to_crlf(new)
        if n == 0:
            raise ToolError("文件里没有找到 old_string：要和文件内容一字不差（包括缩进），可以先用 read_file 看一下")
        if n > 1:
            raise ToolError(f"old_string 在文件里出现了 {n} 次，必须恰好 1 次：多带几行上下文")
        return text.replace(old, new, 1)
