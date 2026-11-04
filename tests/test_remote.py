"""判分时测试进程和被测进程之间的协议：值怎么传，被测进程不可信时测试进程这边挡住了什么。

被测进程这一端在本进程的线程里跑（Channel.serve），不起子进程；两个真实的沙盒进程见 test_evals.py。
"""

import json
import math
import os
import struct
import sys
import threading
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from boxcode.evals.remote import OPS, WORKER_OPS, Channel, RemoteError

Connect = Callable[[str], Any]


@pytest.fixture
def connect(tmp_path: Path) -> Iterator[Connect]:
    """connect(源码)：在“被测进程”里导入这段源码，返回测试进程这边拿到的模块代理。"""
    saved_path = list(sys.path)
    fds: list[int] = []
    names: list[str] = []

    def make(source: str) -> Any:
        name = f"victim_{uuid.uuid4().hex}"
        (tmp_path / f"{name}.py").write_text(source)
        tester_r, worker_w = os.pipe()
        worker_r, tester_w = os.pipe()
        fds.extend([tester_r, tester_w, worker_r, worker_w])
        names.append(name)
        worker = Channel(worker_r, worker_w, WORKER_OPS, tracebacks=True)
        threading.Thread(target=worker.serve, daemon=True).start()
        return Channel(tester_r, tester_w, OPS, tracebacks=False).request("import", name, [str(tmp_path)])

    yield make
    for fd in fds:  # 先关掉测试进程那端，被测进程的 serve 读到 EOF 就退出
        os.close(fd)
    sys.path[:] = saved_path
    for name in names:
        sys.modules.pop(name, None)


def test_plain_values_copied(connect: Connect) -> None:
    mod = connect("def echo(*args, **kwargs):\n    return args, kwargs\n")
    args, kwargs = mod.echo(1, 2.5, "s", b"\x00\xff", None, True, [1, (2,)], {3: {4}}, frozenset({5}), key="v")
    assert args == (1, 2.5, "s", b"\x00\xff", None, True, [1, (2,)], {3: {4}}, frozenset({5}))
    assert type(args[6][1]) is tuple and kwargs == {"key": "v"}
    assert mod.echo("中文", "\ud800")[0] == ("中文", "\ud800")  # 落单的代理字符也传得过去
    assert math.isnan(mod.echo(float("nan"))[0][0])


def test_exceptions_keep_their_types(connect: Connect) -> None:
    mod = connect(
        "class WindowError(ValueError):\n    pass\n"
        "def check(n):\n"
        "    if n < 0:\n        raise WindowError(f'bad {n}')\n"
        "    return {}[n]\n"
    )
    with pytest.raises(mod.WindowError, match="bad -1") as info:
        mod.check(-1)
    assert isinstance(info.value, ValueError) and mod.WindowError is mod.WindowError
    assert any("被测代码的进程里" in note for note in info.value.__notes__)  # 失败时看得到被测代码里是哪一行
    with pytest.raises(KeyError):
        mod.check(1)


def test_objects_stay_in_their_process(connect: Connect) -> None:
    mod = connect(
        "class Box:\n"
        "    def __init__(self, v):\n        self.v = v\n"
        "    def __eq__(self, other):\n        return isinstance(other, Box) and other.v == self.v\n"
        "    __hash__ = None\n"
        "def gen(n):\n    yield from range(n)\n"
    )
    box = mod.Box(3)
    assert box.v == 3 and isinstance(box, mod.Box) and box == mod.Box(3) and box != mod.Box(4)
    box.v = 5
    assert box.v == 5
    assert list(mod.gen(3)) == [0, 1, 2] and mod.Box is mod.Box  # 同一个对象取两次是同一个代理


def test_always_equal_objects_not_trusted(connect: Connect) -> None:
    # 和测试进程里的东西比较不交给被测代码的 __eq__：否则返回一个 __eq__ 总是 True 的对象就能让所有断言通过
    mod = connect(
        "import enum\n"
        "class Anything:\n"
        "    def __eq__(self, other):\n        return True\n"
        "    def __ne__(self, other):\n        return False\n"
        "class AnyList(list):\n"
        "    def __eq__(self, other):\n        return True\n"
        "class Color(enum.IntEnum):\n    RED = 1\n"
        "def anything():\n    return Anything()\n"
        "def any_list():\n    return AnyList([9])\n"
    )
    assert (mod.anything() == [1.5]) is False and (mod.anything() != [1.5]) is True
    with pytest.raises(TypeError):
        assert mod.anything() < 3
    assert mod.any_list() != [1] and mod.any_list() == [9]  # list 的子类按普通数据的拷贝比较
    assert mod.Color.RED == 1 and mod.Color.RED != 2
    assert mod.anything() == mod.anything()  # 两边都是被测进程里的对象：交给被测代码自己判断


def test_tested_code_cannot_reach_into_test_process(connect: Connect) -> None:
    # 测试交过去的函数只能被调用：取得到属性的话，顺着 __globals__ 就能拿到测试进程里的 os 模块
    mod = connect(
        "def call(f, x):\n    return f(x)\n"
        "def peek(f):\n    return f.__globals__\n"
    )
    assert mod.call(lambda x: x * 2, 21) == 42
    with pytest.raises(AttributeError):
        mod.peek(lambda: None)


def test_non_exception_errors_do_not_stop_pytest(connect: Connect) -> None:
    mod = connect("import sys\ndef bye():\n    sys.exit(0)\ndef ctrl_c():\n    raise KeyboardInterrupt\n")
    with pytest.raises(RemoteError, match="SystemExit"):
        mod.bye()
    with pytest.raises(RemoteError, match="KeyboardInterrupt"):
        mod.ctrl_c()


def _frame(obj: Any) -> bytes:
    data = json.dumps(obj).encode()
    return struct.pack(">I", len(data)) + data


def _fake_worker(reply: bytes | None) -> Channel:
    """读一个请求，回复 reply 里的原始字节（None：直接退出），返回测试进程这端。"""
    tester_r, worker_w = os.pipe()
    worker_r, tester_w = os.pipe()

    def serve() -> None:
        (n,) = struct.unpack(">I", os.read(worker_r, 4))
        os.read(worker_r, n)
        if reply is not None:
            os.write(worker_w, reply)
        os.close(worker_w)
        os.close(worker_r)

    threading.Thread(target=serve, daemon=True).start()
    return Channel(tester_r, tester_w, OPS, tracebacks=False)


@pytest.mark.parametrize(("reply", "error"), [
    (None, "已经退出"),
    (_frame({"id": 1, "ok": {"$builtin": "eval"}}), "内置类型"),  # 只认内置的类型，eval、open 这些函数不行
    (_frame({"id": 1, "ok": {"$yours": 12345}}), "不存在的对象"),  # 冒充测试进程交过去的对象
    (_frame({"id": 1, "ok": {"$dict": [[[1], 2]]}}), "看不懂"),  # 列表当 key
    (_frame({"id": 2, "ok": None}), "对不上"),
    (_frame({"id": 1, "error": {"type": {"$builtin": "SystemExit"}, "args": [0], "message": ""}}), "SystemExit"),
    (struct.pack(">I", 2**31), "太大"),
    (b"\x00\x00\x00\x05nope!", "看不懂"),
])
def test_forged_replies_rejected(reply: bytes | None, error: str) -> None:
    channel = _fake_worker(reply)
    with pytest.raises(RemoteError, match=error):
        channel.request("getattr", None, "x")
    with pytest.raises(RemoteError):  # 坏过一次就不再用这条连接
        channel.request("getattr", None, "x")
