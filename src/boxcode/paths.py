"""路径的几个基本操作：沙盒规则、工作区检查、文件工具都靠它们判断“是不是在工作区里”。

macOS 上要注意两件事：
- APFS 默认不区分大小写，但 Path.resolve() 不改大小写：/users/PYKE 和 /Users/pyke 是同一个目录。
  所以比较一律不区分大小写，存在的路径先换成磁盘上真实的大小写（F_GETPATH）
- “先检查路径、再打开”中间有空档：沙盒里脱离了进程组的后台进程可以在这时把文件换成指向别处的符号链接。
  所以文件工具检查的是已经打开的文件描述符的真实位置（fd_path），见 tools/base.py 的 open_in_workspace
"""

import fcntl
import os
from pathlib import Path

_F_GETPATH: int | None = getattr(fcntl, "F_GETPATH", None)  # 只有 macOS 有


def fd_path(fd: int) -> Path:
    """文件描述符实际指向的路径（内核给的，已经解析了所有链接，大小写是磁盘上真实的）。"""
    if _F_GETPATH is not None:
        raw = fcntl.fcntl(fd, _F_GETPATH, bytes(1024))
        return Path(os.fsdecode(raw.rstrip(b"\0")))
    return Path(f"/proc/self/fd/{fd}").readlink()  # Linux


def canonical(path: Path) -> Path:
    """解析链接，并且换成磁盘上真实的大小写。不存在的路径只能 resolve。"""
    try:
        p = path.resolve()
    except (OSError, RuntimeError):  # 符号链接循环
        return path.absolute()
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return p
    try:
        return fd_path(fd)
    except OSError:
        return p
    finally:
        os.close(fd)


def path_key(p: Path) -> tuple[str, ...]:
    return tuple(part.casefold() for part in p.parts)


def is_inside(p: Path, root: Path) -> bool:
    """p 是 root 或者在 root 下面（不区分大小写，不解析链接：调用方先 canonical）。"""
    k, r = path_key(p), path_key(root)
    return k[: len(r)] == r
