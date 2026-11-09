"""工具的公共部分：参数用 Pydantic 声明，自动生成给模型的 JSON Schema，也用它校验模型给的参数。"""

import contextlib
import errno
import os
import stat
import threading
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, ClassVar

from pydantic import BaseModel, ConfigDict

from boxcode.config import Settings
from boxcode.llm.base import ToolSpec
from boxcode.paths import canonical, fd_path, path_key
from boxcode.sandbox import SandboxRunner


class Risk(StrEnum):
    READ = "read"  # 只读工作区
    WRITE = "write"  # 改工作区里的文件
    EXEC = "exec"  # 在沙盒里执行命令


class ToolError(Exception):
    """工具执行失败，原因会作为工具结果回给模型，让它自己调整。"""


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    runner: SandboxRunner
    settings: Settings
    # 被设置后，正在执行的命令会被杀掉（界面上按了“停止”）
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass(frozen=True)
class ToolResult:
    text: str
    ok: bool = True


@dataclass(frozen=True)
class Target:
    """这次调用会碰到什么，给权限策略判断用。"""

    paths: tuple[Path, ...] = ()
    command: str | None = None


class ToolParams(BaseModel):
    """所有工具参数的基类：多给的字段直接报错（例如把 timeout_s 写成 timeout），而不是悄悄忽略。"""

    model_config = ConfigDict(extra="forbid")


class Tool[P: ToolParams](ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    risk: ClassVar[Risk]
    Params: type[P]

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.Params.model_json_schema())

    def parse(self, arguments: str) -> P:
        """模型给的 JSON 字符串 → 参数。不合法时抛 pydantic.ValidationError。"""
        return self.Params.model_validate_json(arguments or "{}")

    def target(self, ctx: ToolContext, params: P) -> Target:
        """会写文件、执行命令的工具要覆盖它，权限策略按这里返回的东西判断。不覆盖的话每次调用都要问人。"""
        return Target()

    @abstractmethod
    def run(self, ctx: ToolContext, params: P) -> ToolResult: ...


def in_workspace(workspace: Path, p: Path) -> bool:
    """解析链接后是否仍在工作区里。符号链接循环（resolve 会抛 RuntimeError）当作不在。"""
    try:
        rp = p.resolve()
        ws = workspace.resolve()
    except (OSError, RuntimeError):
        return False
    return rp == ws or ws in rp.parents


def resolve_in_workspace(workspace: Path, path: str) -> Path:
    """相对路径按工作区解析；解析链接后必须仍在工作区里，否则拒绝（防止 ../ 和指向外面的链接）。

    只适合给权限策略看、给模型报错：真正读写文件要用 open_in_workspace，检查和打开之间可能被换成链接。
    """
    try:
        p = (workspace / path).resolve()
    except (OSError, RuntimeError) as e:  # 符号链接循环、路径太长
        raise ToolError(f"路径解析不了：{path}（{e}）") from e
    if not in_workspace(workspace, p):
        raise ToolError(f"路径不在工作区内：{path}")
    return p


def _check_fd(ws_key: tuple[str, ...], fd: int, path: str, write: bool) -> None:
    """已经打开的文件或目录真的在工作区里；要写的话还不能在任何一层 .git 里。"""
    key = path_key(fd_path(fd))
    if key[: len(ws_key)] != ws_key:
        raise ToolError(f"路径不在工作区内：{path}（打开时它指向了工作区外）")
    if write and ".git" in key[len(ws_key):]:
        raise ToolError(f"受保护的位置：{path}（打开时它指向了 .git）")


@contextlib.contextmanager
def open_in_workspace(workspace: Path, path: str, *, write: bool = False, create: bool = False) -> Iterator[BinaryIO]:
    """打开工作区里的一个普通文件，检查和打开之间不留空档。

    文件工具在沙盒外执行，沙盒里用 setsid 脱离了进程组的后台进程能活过命令结束，一直把某个文件来回换成
    指向工作区外（或 .git）的符号链接。先 resolve 检查、再按路径打开，就可能在中间被换掉（红队实测：
    读到工作区外的文件、写进 ~/.zshrc 和 .git/hooks）。所以这里：
    - 从工作区目录开始，每一级目录都相对上一级已经打开的目录 fd 打开，并检查 fd 的真实位置（fd_path）
    - 最后一级用 O_NOFOLLOW 打开：这时它是符号链接就直接失败；只接受普通文件（FIFO 会让读卡住）
    - 打开之后再查一次真实位置。写的时候不带 O_TRUNC 打开，确认位置之后才截断
    """
    p = resolve_in_workspace(workspace, path)
    root = workspace.resolve()
    ws_key = path_key(canonical(root))
    parts = p.relative_to(root).parts
    if not parts:
        raise ToolError(f"不是文件：{path}")
    dfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            try:
                nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY, dir_fd=dfd)
            except FileNotFoundError:
                if not create:
                    raise ToolError(f"目录不存在：{path}") from None
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, dir_fd=dfd)
                nfd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dfd)
            except NotADirectoryError:
                raise ToolError(f"路径中间有一段不是目录：{path}") from None
            os.close(dfd)
            dfd = nfd
            _check_fd(ws_key, dfd, path, write)
        flags = (os.O_RDWR | (os.O_CREAT if create else 0)) if write else (os.O_RDONLY | os.O_NONBLOCK)
        try:
            fd = os.open(parts[-1], flags | os.O_NOFOLLOW, 0o666, dir_fd=dfd)
        except FileNotFoundError:
            raise ToolError(f"文件不存在：{path}") from None
        except OSError as e:
            if e.errno == errno.ELOOP:
                raise ToolError(f"{path} 在打开时是符号链接，不跟随") from None
            if e.errno == errno.EISDIR:
                raise ToolError(f"不是文件：{path}") from None
            raise
    finally:
        os.close(dfd)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ToolError(f"不是普通文件：{path}")
        _check_fd(ws_key, fd, path, write)
        os.set_blocking(fd, True)
        f = os.fdopen(fd, "r+b" if write else "rb")
    except BaseException:
        os.close(fd)
        raise
    with f:
        yield f


def truncate(text: str, limit: int) -> str:
    """保留开头和结尾：报错信息常在最后。"""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n\n... [省略 {len(text) - 2 * half} 个字符] ...\n\n{text[-half:]}"
