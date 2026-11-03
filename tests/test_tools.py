from pathlib import Path

import pytest

from boxcode.config import Settings
from boxcode.sandbox import NoSandboxRunner
from boxcode.tools import EditFile, Grep, ListDir, ReadFile, ToolContext, ToolError


@pytest.fixture
def ctx(workspace: Path, settings: Settings) -> ToolContext:
    (workspace / "a.py").write_text("x = 1\ny = 2\n")
    return ToolContext(workspace, NoSandboxRunner(), settings)


def test_read_file_numbers_lines(ctx: ToolContext) -> None:
    out = ReadFile().run(ctx, ReadFile.Params(path="a.py")).text
    assert "    1\tx = 1" in out and "    2\ty = 2" in out


def test_path_escape_rejected(ctx: ToolContext) -> None:
    with pytest.raises(ToolError):
        ReadFile().run(ctx, ReadFile.Params(path="../../etc/passwd"))


def test_symlink_escape_rejected(ctx: ToolContext, tmp_path: Path) -> None:
    (tmp_path / "outside.txt").write_text("secret")
    (ctx.workspace / "link.txt").symlink_to(tmp_path / "outside.txt")
    with pytest.raises(ToolError):
        ReadFile().run(ctx, ReadFile.Params(path="link.txt"))


def test_edit_requires_unique_match(ctx: ToolContext) -> None:
    (ctx.workspace / "b.py").write_text("a\na\n")
    with pytest.raises(ToolError):
        EditFile().run(ctx, EditFile.Params(path="b.py", old_string="a", new_string="b"))
    EditFile().run(ctx, EditFile.Params(path="a.py", old_string="y = 2", new_string="y = 3"))
    assert (ctx.workspace / "a.py").read_text() == "x = 1\ny = 3\n"


def test_grep_and_list(ctx: ToolContext) -> None:
    assert "a.py:2: y = 2" in Grep().run(ctx, Grep.Params(pattern=r"y =")).text
    assert "a.py" in ListDir().run(ctx, ListDir.Params()).text
