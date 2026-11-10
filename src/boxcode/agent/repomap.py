"""代码库地图：文件清单加每个文件的主要类和函数，运行开始时一次性交给模型，减少盲目的 list_dir 和读文件。

在 Agent 进程里执行，不经过沙盒，而且仓库是不可信的：
- 只解析、不执行：Python 用 ast，其他语言按行匹配简单的正则（行长有上限，模式里没有嵌套的量词，不会灾难性回溯）
- 不跟符号链接，读文件走 read_workspace_bytes；隐藏文件（.env 这些）不列
- 不调 git：别人的仓库可以用 core.fsmonitor 让 git 执行任意命令，所以也就没有用 .gitignore
- 文件数、单个文件大小、总耗时都有上限，长度超了就逐级减少细节

文件名和符号名都来自仓库，可能被人埋指令：地图只能放在用户消息里，并且包在带随机后缀的标签里（见 context.py）。
"""

import ast
import re
import stat
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

from boxcode.tools.base import ToolError
from boxcode.tools.fs import display, read_workspace_bytes, split_lines, walk_workspace

SKIP_NAMES = {"dist", "build", "target", "coverage", "htmlcov", "site-packages", "vendor"}
# 最多看这么多个文件和目录
MAX_ENTRIES = 5000
MAX_SCAN_SECONDS = 2.0
# 比这大的文件不解析符号（多半是生成的代码）：ast 树很占内存，1 MB 的 `a;` 实测吃掉 1.1 GB
MAX_SYMBOL_BYTES = 200 * 1024
# 正则只看每行开头这么多字符
MAX_LINE_CHARS = 300
MAX_FILE_SYMBOLS = 60
MAX_CLASS_MEMBERS = 20

# 细节级别：0 类和方法都列，1 只列顶层，2 只列路径，3 路径也列不全
DETAIL_FULL, DETAIL_TOP_LEVEL, DETAIL_PATHS, DETAIL_PARTIAL_PATHS = range(4)

_JS_PATTERNS = (
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)"), "()"),
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"), ""),
    (re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)"), ""),
    (re.compile(r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_$][\w$]*)"), ""),
)
_GO_PATTERNS = (
    (re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)"), "()"),
    (re.compile(r"^type\s+(\w+)\s"), ""),
)
_RUST_PATTERNS = (
    (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)"), "()"),
    (re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait)\s+(\w+)"), ""),
)
_JAVA_PATTERNS = ((re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_]\w*)"), ""),)
PATTERNS: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    ".js": _JS_PATTERNS, ".jsx": _JS_PATTERNS, ".mjs": _JS_PATTERNS, ".ts": _JS_PATTERNS, ".tsx": _JS_PATTERNS,
    ".go": _GO_PATTERNS, ".rs": _RUST_PATTERNS, ".java": _JAVA_PATTERNS, ".kt": _JAVA_PATTERNS, ".cs": _JAVA_PATTERNS,
}
CODE_SUFFIXES = {".py", *PATTERNS}


@dataclass(frozen=True)
class RepoMap:
    text: str
    files: int
    symbols: int
    detail: int  # 用了哪个细节级别
    complete: bool  # False：文件太多或者超时，没看完整个仓库
    seconds: float


@dataclass(frozen=True)
class _Symbol:
    name: str
    members: tuple[str, ...] = ()


@dataclass(frozen=True)
class _File:
    path: str
    lines: int | None = None  # 不是代码文件时没有
    symbols: tuple[_Symbol, ...] = ()


def python_symbols(source: bytes) -> tuple[_Symbol, ...]:
    """语法不对的文件（可能正是要修的）照样列出路径，只是没有符号。

    先按 UTF-8 解码再解析：传字节的话解析器会照文件头的 `# coding:` 选解码器，punycode 这种纯 Python 的解码器
    是平方复杂度，实测 780 KB 的文件卡 47 秒。不是 UTF-8 的文件只是没有符号。
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # 字符串里的无效转义（"\d"）每处一条 SyntaxWarning，会刷满终端
            tree = ast.parse(source.decode())
    except (SyntaxError, ValueError, RecursionError, MemoryError):  # UnicodeDecodeError 是 ValueError
        return ()
    symbols = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            symbols.append(_Symbol(f"{node.name}()"))
        elif isinstance(node, ast.ClassDef):
            members = tuple(f"{m.name}()" for m in node.body if isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef)
                            and not (m.name.startswith("__") and m.name.endswith("__")))
            symbols.append(_Symbol(node.name, members))
    return tuple(symbols)


def pattern_symbols(text: str, patterns: tuple[tuple[re.Pattern[str], str], ...]) -> tuple[_Symbol, ...]:
    names: dict[str, None] = {}  # 去重并保持顺序
    for line in split_lines(text):
        head = line[:MAX_LINE_CHARS]
        for pattern, suffix in patterns:
            if (m := pattern.search(head)) is not None:
                names[m[1] + suffix] = None
                break
    return tuple(_Symbol(name) for name in names)


def _parse_file(workspace: Path, rel: str, suffix: str) -> _File:
    try:
        data = read_workspace_bytes(workspace, rel)
    except (ToolError, OSError):
        return _File(display(rel))
    if b"\0" in data:
        return _File(display(rel))
    lines = data.count(b"\n") + (not data.endswith(b"\n") and bool(data))
    if suffix == ".py":
        symbols = python_symbols(data)
    else:
        symbols = pattern_symbols(data.decode(errors="replace"), PATTERNS[suffix])
    return _File(display(rel), lines, symbols)


def _collect(workspace: Path) -> tuple[list[_File], bool]:
    """返回看到的文件，和有没有看完。"""
    files: list[_File] = []
    deadline = time.monotonic() + MAX_SCAN_SECONDS
    seen = 0
    stopped = False

    def skip_dir(name: str) -> bool:
        return name.startswith(".") or name.casefold() in SKIP_NAMES

    def over_budget() -> bool:
        nonlocal seen, stopped
        seen += 1
        stopped = stopped or seen > MAX_ENTRIES or time.monotonic() > deadline
        return stopped

    for p in walk_workspace(workspace, workspace, skip_dir, over_budget):
        if p.name.startswith("."):
            continue
        try:
            st = p.lstat()
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue  # 目录由文件的路径体现；符号链接不跟
        rel = p.relative_to(workspace).as_posix()
        suffix = p.suffix.lower()
        if suffix in CODE_SUFFIXES and st.st_size <= MAX_SYMBOL_BYTES:
            files.append(_parse_file(workspace, rel, suffix))
        else:
            files.append(_File(display(rel)))
    return files, not stopped


def _render_symbol(symbol: _Symbol, detail: int) -> str:
    if detail != DETAIL_FULL or not symbol.members:
        return symbol.name
    shown = list(symbol.members[:MAX_CLASS_MEMBERS])
    if len(symbol.members) > MAX_CLASS_MEMBERS:
        shown.append(f"+{len(symbol.members) - MAX_CLASS_MEMBERS} more")
    return f"{symbol.name} {{{', '.join(shown)}}}"


def _render_file(f: _File, detail: int) -> str:
    head = f"{f.path} [{f.lines} lines]" if f.lines is not None else f.path
    if detail >= DETAIL_PATHS or not f.symbols:
        return head
    parts = [_render_symbol(s, detail) for s in f.symbols[:MAX_FILE_SYMBOLS]]
    if len(f.symbols) > MAX_FILE_SYMBOLS:
        parts.append(f"+{len(f.symbols) - MAX_FILE_SYMBOLS} more")
    return f"{head}: {', '.join(parts)}"


def _fit(files: list[_File], max_chars: int) -> tuple[str, int]:
    """细节从多到少，用放得下的最详细的一级；路径都放不下时只列前面的，并说明还有多少。"""
    for detail in (DETAIL_FULL, DETAIL_TOP_LEVEL, DETAIL_PATHS):
        text = "\n".join(_render_file(f, detail) for f in files)
        if len(text) <= max_chars:
            return text, detail
    shown: list[str] = []
    used = 0
    for f in files:
        line = _render_file(f, DETAIL_PATHS)
        if used + len(line) + 1 > max_chars:
            break
        shown.append(line)
        used += len(line) + 1
    shown.append(f"... {len(files) - len(shown)} more files not shown")
    return "\n".join(shown), DETAIL_PARTIAL_PATHS


def build_repo_map(workspace: Path, max_chars: int) -> RepoMap | None:
    """没有文件时返回 None。"""
    t0 = time.monotonic()
    files, complete = _collect(workspace)
    if not files:
        return None
    text, detail = _fit(files, max_chars)
    if not complete:
        text += "\n... the scan stopped early; other files exist"
    symbols = sum(len(f.symbols) + sum(len(s.members) for s in f.symbols) for f in files)
    return RepoMap(text, len(files), symbols, detail, complete, round(time.monotonic() - t0, 3))
