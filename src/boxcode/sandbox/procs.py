"""找出并杀掉某一条命令的 Seatbelt 沙盒里的所有进程，包括用 setsid、setpgid 脱离了进程组的。

只杀进程组不够：沙盒里的代码可以 setsid、setpgid，或者 posix_spawn 时设 POSIX_SPAWN_SETSID，
脱离进程组的进程会在命令结束后接着在沙盒里跑（改工作区、改判分目录、和文件工具抢着换符号链接）。
沙盒却脱离不了：子进程、exec 之后都继承同一个沙盒。所以每条命令的规则里带一条独一无二的标记

    (deny mach-lookup (global-name "com.boxcode.sandbox.<随机>"))

沙盒外的 BoxCode 用 sandbox_check 逐个问系统里的进程“这个名字能不能查”：只有这条命令沙盒里的进程会被拒绝。
再问一个只差一个后缀的名字，必须能查：一律拒绝 mach-lookup 的沙盒（很多 App 的沙盒就是这样）不算进来。
没有这个服务，规则不影响命令本身；沙盒里的代码改不了已经套上的规则，也就藏不起来。

sandbox_check 的路径类检查对不存在的路径总是返回“拒绝”，所以标记用服务名，不用文件路径。
"""

import contextlib
import ctypes
import functools
import os
import secrets
import signal
import sys

MARKER_PREFIX = "com.boxcode.sandbox."
# libsystem_sandbox 的 sandbox_filter_type 和标志位
_FILTER_GLOBAL_NAME = 2
_CHECK_NO_REPORT = 0x40000000  # 只是问一下，不往系统日志里写拒绝记录
# 一轮里刚 fork 出来、还没被杀到的进程下一轮再杀；一直杀不完（fork 炸弹）也不无限循环
MAX_ROUNDS = 100


def new_marker() -> str:
    return MARKER_PREFIX + secrets.token_hex(16)


def marker_rule(marker: str) -> str:
    return f'(deny mach-lookup (global-name "{marker}"))'


@functools.cache
def _libsystem() -> ctypes.CDLL:
    lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    # int sandbox_check(pid_t, const char *operation, int type, ...)：只声明固定参数，
    # 多传的那个会按可变参数传（Apple 的 arm64 上可变参数放在栈上，和普通参数不一样）
    lib.sandbox_check.restype = ctypes.c_int
    lib.sandbox_check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    lib.proc_listallpids.restype = ctypes.c_int
    lib.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
    return lib


def _lookup_denied(pid: int, name: bytes) -> bool:
    flags = _FILTER_GLOBAL_NAME | _CHECK_NO_REPORT
    return bool(_libsystem().sandbox_check(pid, b"mach-lookup", flags, ctypes.c_char_p(name)) == 1)


def in_sandbox(pid: int, marker: str) -> bool:
    name = marker.encode()
    return _lookup_denied(pid, name) and not _lookup_denied(pid, name + b".x")


def _all_pids() -> list[int]:
    lib = _libsystem()
    n = lib.proc_listallpids(None, 0)
    if n <= 0:
        return []
    buf = (ctypes.c_int * (n + 256))()  # 两次调用之间可能又多了进程
    n = lib.proc_listallpids(buf, ctypes.sizeof(buf))
    return [pid for pid in buf[: max(n, 0)] if pid > 0]


def kill_sandbox(marker: str) -> int:
    """SIGKILL 这个沙盒里的每一个进程，返回杀了几个。一边找一边杀，直到一整轮一个都找不到。"""
    if sys.platform != "darwin":
        return 0
    me = os.getpid()
    killed: set[int] = set()
    for _ in range(MAX_ROUNDS):
        found = 0
        for pid in _all_pids():
            # 杀过的不再管：可能还没死透，或者已经是等着被回收的僵尸
            if pid == me or pid in killed or not in_sandbox(pid, marker):
                continue
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)
            killed.add(pid)
            found += 1
        if not found:
            break
    return len(killed)
