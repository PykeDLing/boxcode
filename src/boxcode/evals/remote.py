"""判分时把被测代码放进单独的进程。

以前 pytest 和 Agent 写的代码在同一个进程里：被测代码一导入就能改掉报告插件里的数据、换掉 pytest 的内部函数，
伪造出“全部通过”。现在判分起两个进程，各在自己的沙盒里：

- 测试进程（pytest、原题的测试和 conftest、报告插件）：只执行原题自己的代码。导入 editable 里的模块时
  （例如 `from stats import moving_average`），拿到的是代理模块，真正的模块在被测进程里
- 被测进程（`remote.main()`）：导入 Agent 改过的模块，按测试进程的请求取属性、调函数、做运算，
  把结果传回去。它的沙盒对判分目录只读，改不了测试文件和 pytest 配置；也拿不到写报告的那个文件描述符

两边通过两根管道交换 JSON 消息（4 字节长度 + 内容）。传过去的值：
- 普通数据（None、bool、int、float、str、bytes 和由它们组成的 list、tuple、dict、set、frozenset）按值复制
- 别的对象（函数、类、实例、生成器……）留在原来的进程里，对面拿到一个代理，对代理的调用和运算都转发回来
- 异常按类型和参数重建：内置异常还是原来的类，被测代码自己定义的异常类在测试进程里有一个对应的子类
  （继承它最近的内置异常基类），所以 pytest.raises(ValueError) 和 pytest.raises(stats.WindowError) 都照常能用

测试进程不信任对面发来的任何东西：只解析 JSON，不执行对面给的代码；对面能请求的只有对测试交过去的对象做调用和几种运算，
内置类型不能当操作目标（`type(名字, 基类, 属性)` 能在测试进程里造出一个 `__eq__` 由被测代码决定的真对象），
取不了测试进程里对象的属性（取得到的话顺着 `f.__globals__` 就能拿到 os 模块）。被测代码里抛出的 SystemExit、
KeyboardInterrupt 这类不是 Exception 的异常，传回来一律变成 RemoteError，不会让 pytest 退出。

比较运算单独处理：被测进程里的对象和测试进程里的东西（列表、数字、pytest.approx……）比较时，不交给被测代码的
`__eq__` 判断，按“类型不同”处理。否则返回一个 `__eq__` 总是 True 的对象，就能让所有 `assert f(x) == 期望值` 通过。
int、str、tuple 这些类型的子类（IntEnum、namedtuple、numpy 的 float64）会顺带传一份普通数据的拷贝，
和测试进程里的东西比较时用这份拷贝、在测试进程里算。两边都是被测进程里的对象时（`Point(1, 2) == Point(1, 2)`），
才交给被测代码自己判断。`in` 也一样：有拷贝的按拷贝算；没有拷贝的自定义类，它的 `__contains__` 本身就是被测的行为。

不支持的：测试 monkeypatch 被测模块（只改得到测试进程里的代理）；被测代码在别的线程里回调测试交过去的函数；
被测代码返回的对象和测试自己（不是 editable 的模块里）构造的对象在两个进程里，不会相等。
"""

import base64
import builtins
import contextlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import itertools
import json
import operator
import os
import struct
import sys
import threading
import traceback
import types
from collections.abc import Callable, Iterable, Sequence
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

# 环境变量。测试进程：管道的 fd（读,写）、判分目录、editable、写报告的 fd；被测进程：管道的 fd（读,写）。
# 两边用不同的名字：被测进程也会导入 boxcode.evals，不能让它以为自己是测试进程
TESTER_FDS_ENV = "BOXCODE_TESTER_FDS"
WORKER_FDS_ENV = "BOXCODE_WORKER_FDS"
CHECK_DIR_ENV = "BOXCODE_CHECK_DIR"
EDITABLE_ENV = "BOXCODE_EDITABLE"
REPORT_FD_ENV = "BOXCODE_REPORT_FD"

MAX_MESSAGE = 64 * 1024 * 1024
MAX_TEXT = 20_000  # 异常消息、调用栈最多传这么多字符
_HEADER = struct.Struct(">I")
_MISSING = object()


class RemoteError(Exception):
    """被测进程出了问题：退出了、发来看不懂的消息，或者抛出了 SystemExit 这类不是 Exception 的异常。"""


def is_editable(patterns: Iterable[str], rel: str) -> bool:
    """rel 是不是 editable 里的文件。APFS 默认不区分大小写，比较时也不区分，否则 Pytest.ini 这种名字能绕过。"""
    name = rel.casefold()
    return any(fnmatchcase(name, pattern.casefold()) for pattern in patterns)


def _exit(obj: Any, exc: BaseException | None) -> Any:
    if exc is None:
        return type(obj).__exit__(obj, None, None, None)
    return type(obj).__exit__(obj, type(exc), exc, exc.__traceback__)


_ARITHMETIC = {
    "add": operator.add, "sub": operator.sub, "mul": operator.mul, "matmul": operator.matmul,
    "truediv": operator.truediv, "floordiv": operator.floordiv, "mod": operator.mod, "pow": operator.pow,
    "lshift": operator.lshift, "rshift": operator.rshift, "and": operator.and_, "or": operator.or_,
    "xor": operator.xor,
}
_COMPARISONS = {"eq": operator.eq, "ne": operator.ne, "lt": operator.lt, "le": operator.le, "gt": operator.gt,
                "ge": operator.ge}
# 两边都能请求对面做的运算（第一个参数一般是对面的对象）
OPS: dict[str, Callable[..., Any]] = {
    "call": lambda f, *args, **kwargs: f(*args, **kwargs),
    "repr": repr, "str": str, "bool": bool, "len": len, "hash": hash, "iter": iter, "next": next,
    "reversed": reversed, "format": format, "index": operator.index, "int": int, "float": float, "dir": dir,
    "contains": operator.contains, "getitem": operator.getitem, "setitem": operator.setitem,
    "delitem": operator.delitem, "neg": operator.neg, "pos": operator.pos, "abs": abs, "invert": operator.invert,
    "isinstance": isinstance, "issubclass": issubclass, "enter": lambda obj: type(obj).__enter__(obj), "exit": _exit,
    **_ARITHMETIC, **_COMPARISONS,
}
# 这些运算里代理可能在第二个位置（`1 + 代理`、`isinstance(x, 代理)`），其余的操作目标都是第一个参数
_EITHER_OPERAND = frozenset({*_ARITHMETIC, "isinstance", "issubclass"})


def _import(name: str, paths: list[str]) -> types.ModuleType:
    if not isinstance(name, str) or not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise TypeError("import 的参数不对")
    for p in reversed(paths):  # 和测试进程一样的搜索路径（判分目录里的那几项）
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module(name)


def _public_names(module: Any) -> list[str]:
    names = getattr(module, "__all__", None)
    if names is None:
        names = [n for n in dir(module) if not n.startswith("_")]
    return [n for n in names if isinstance(n, str)]


# 只有被测进程提供的操作：测试进程不让对面取属性、导入模块
WORKER_OPS: dict[str, Callable[..., Any]] = {
    **OPS, "getattr": getattr, "setattr": setattr, "delattr": delattr, "import": _import,
    "public_names": _public_names,
}

# 按值传的类型：只认这几个类型本身，子类（IntEnum、namedtuple）当成别的对象，见 _SNAPSHOTS
_SCALARS = (type(None), bool, int, float, str)
_SNAPSHOTS: tuple[tuple[type, Callable[[Any], Any]], ...] = (
    (str, str.__str__), (int, int.__int__), (float, float.__float__), (bytes, bytes), (tuple, tuple),
    (list, list), (dict, dict), (frozenset, frozenset), (set, set),
)


def _describe(obj: Any) -> str:
    with contextlib.suppress(Exception):
        name = obj.__qualname__ if isinstance(obj, type | types.FunctionType | types.BuiltinFunctionType) else None
        return str(name or type(obj).__qualname__)[:200]
    return "object"


def _text(e: BaseException) -> str:
    try:
        return str(e)[:MAX_TEXT]
    except Exception:
        return type(e).__name__


class Channel:
    """连接的一端：发请求、等回复，等回复时对面发来的请求（回调）也在这里处理。

    两边各自记着交给对面的对象（编号 → 对象）和对面的对象的代理（编号 → 代理），同一个对象只编一次号，
    所以同一个函数取两次是同一个代理，`is` 照常能用。
    """

    def __init__(
        self, rfd: int, wfd: int, ops: dict[str, Callable[..., Any]], *, tracebacks: bool, exports_only: bool,
    ) -> None:
        self._rfd, self._wfd = rfd, wfd
        self._ops = ops
        self._tracebacks = tracebacks  # 被测进程把调用栈附在异常里，测试失败时看得到是哪一行
        self._exports_only = exports_only  # 测试进程：对面只能操作这边交过去的对象
        self._lock = threading.RLock()
        self._request_ids = itertools.count(1)
        self._export_ids = itertools.count(1)
        self._exports: dict[int, Any] = {}
        self._exported: dict[int, int] = {}  # id(对象) → 编号；_exports 拿着对象，id 不会被别的对象重用
        self._proxies: dict[int, Any] = {}
        self._stand_ins: dict[type, int] = {}  # 对面的异常类在这边的对应子类 → 对面的编号
        self._broken: str | None = None

    # ---- 收发 ----

    def _send(self, msg: dict[str, Any]) -> None:
        data = json.dumps(msg).encode()  # 转成 \uXXXX：字符串里落单的代理字符也编得出来
        if len(data) > MAX_MESSAGE:
            raise RemoteError(f"要传的数据超过 {MAX_MESSAGE // 1024 // 1024} MB")
        view = memoryview(_HEADER.pack(len(data)) + data)
        while view:
            view = view[os.write(self._wfd, view):]

    def _read_exact(self, n: int) -> bytes:
        chunks: list[bytes] = []
        while n:
            chunk = os.read(self._rfd, min(n, 1 << 20))
            if not chunk:
                raise EOFError
            chunks.append(chunk)
            n -= len(chunk)
        return b"".join(chunks)

    def _recv(self) -> dict[str, Any]:
        (n,) = _HEADER.unpack(self._read_exact(_HEADER.size))
        if n > MAX_MESSAGE:
            raise RemoteError("对面发来的消息太大")
        msg = json.loads(self._read_exact(n))
        if not isinstance(msg, dict) or type(msg.get("id")) is not int:
            raise RemoteError("对面发来的消息格式不对")
        return msg

    def request(self, op: str, /, *args: Any, **kwargs: Any) -> Any:
        """请对面做 op（OPS 里的运算，或者被测进程才有的 getattr、import……），返回结果。"""
        with self._lock:
            if self._broken is not None:
                raise RemoteError(self._broken)
            # 编码会登记交给对面的对象，也要在锁里：测试可能在几个线程里同时调用
            payload = {"op": op, "args": self.encode(list(args)), "kwargs": self.encode(kwargs)}
            try:
                mid = next(self._request_ids)
                self._send({"id": mid, **payload})
                while True:
                    msg = self._recv()
                    if "op" not in msg:
                        break
                    self._handle(msg)  # 等回复的时候对面先发来了请求：被测代码在回调测试交过去的函数
                if msg["id"] != mid:
                    raise RemoteError("对面的回复和请求对不上")
                if "error" in msg:
                    error = self._decode_error(msg["error"])
                else:
                    return self.decode(msg.get("ok"))
            except (EOFError, BrokenPipeError):
                self._broken = "被测代码的进程已经退出"
                raise RemoteError(self._broken) from None
            except RemoteError as e:
                self._broken = str(e)
                raise
            except (OSError, ValueError, TypeError, KeyError, RecursionError, struct.error) as e:
                self._broken = f"对面发来的消息看不懂：{type(e).__name__}: {e}"
                raise RemoteError(self._broken) from None
        raise error

    def serve(self) -> None:
        """被测进程的主循环：一直处理请求，直到测试进程那边关掉管道。"""
        while True:
            try:
                msg = self._recv()
            except EOFError:
                return
            if "op" not in msg:
                raise RemoteError("测试进程发来的不是请求")
            self._handle(msg)

    def _handle(self, msg: dict[str, Any]) -> None:
        try:
            op = msg["op"]
            if op not in self._ops:
                raise (AttributeError if op == "getattr" else TypeError)(f"对面不支持 {op!r}")
            args = self.decode(msg.get("args", []))
            kwargs = self.decode(msg.get("kwargs", {}))
            if not (isinstance(args, list) and isinstance(kwargs, dict) and all(isinstance(k, str) for k in kwargs)):
                raise TypeError("请求的参数格式不对")
            if self._exports_only and not self._targets_export(op, args):
                raise TypeError(f"对面只能对这边交过去的对象做 {op!r}")
            reply: dict[str, Any] = {"id": msg["id"], "ok": self.encode(self._ops[op](*args, **kwargs))}
        except BaseException as e:  # 包括被测代码抛出的 SystemExit、KeyboardInterrupt：变成错误回复，进程接着服务
            reply = {"id": msg["id"], "error": self._encode_error(e)}
        try:
            self._send(reply)
        except (RemoteError, ValueError, TypeError, RecursionError) as e:  # 结果传不过去（太大、循环引用）
            self._send({"id": msg["id"], "error": self._encode_error(RemoteError(f"结果传不回去：{e}"))})

    def _targets_export(self, op: str, args: list[Any]) -> bool:
        """操作目标是不是这边交给过对面的。内置类型按名字传，从来不算：`type` 调用不了，`type["x"]` 的别名也拿不到。"""
        targets = args[:2] if op in _EITHER_OPERAND else args[:1]
        return any(id(target) in self._exported for target in targets)  # _exports 拿着对象，id 不会被别的对象重用

    # ---- 编码 ----

    def encode(self, value: Any) -> Any:
        t = type(value)
        if t in _SCALARS:
            return value
        if t is list:
            return [self.encode(v) for v in value]
        if t is dict:
            return {"$dict": [[self.encode(k), self.encode(v)] for k, v in value.items()]}
        if t is tuple or t is set or t is frozenset:
            return {f"${t.__name__}": [self.encode(v) for v in value]}
        if t is bytes:
            return {"$bytes": base64.b64encode(value).decode()}
        if isinstance(value, BaseException):
            return {"$exc": self._encode_error(value)}
        if isinstance(value, Remote) and object.__getattribute__(value, "_boxcode_channel") is self:
            return {"$yours": object.__getattribute__(value, "_boxcode_id")}
        if isinstance(value, type):
            if value in self._stand_ins:
                return {"$yours": self._stand_ins[value]}
            name = str(getattr(value, "__name__", ""))
            if getattr(builtins, name, None) is value:
                return {"$builtin": name}
        return self._export(value)

    def _export(self, value: Any) -> dict[str, Any]:
        ref = self._exported.get(id(value))
        if ref is None:
            ref = next(self._export_ids)
            self._exported[id(value)] = ref
            self._exports[ref] = value
        out: dict[str, Any] = {"$ref": ref, "name": _describe(value)}
        if isinstance(value, type) and issubclass(value, BaseException):
            out["exc"] = [c.__name__ for c in value.__mro__ if getattr(builtins, c.__name__, None) is c]
            out["module"] = str(getattr(value, "__module__", ""))[:200]
            return out
        for base, snapshot in _SNAPSHOTS:
            if isinstance(value, base):
                with contextlib.suppress(Exception):
                    out["value"] = self.encode(snapshot(value))
                break
        return out

    def _encode_error(self, e: BaseException) -> dict[str, Any]:
        try:
            args = self.encode(list(e.args))
        except Exception:
            args = []
        out = {"type": self.encode(type(e)), "args": args, "message": _text(e)}
        if self._tracebacks:
            with contextlib.suppress(Exception):
                out["traceback"] = "".join(traceback.format_exception(e))[-MAX_TEXT:]
        return out

    # ---- 解码：对面发来的东西一律不可信 ----

    def decode(self, value: Any) -> Any:
        t = type(value)
        if t in _SCALARS:
            return value
        if t is list:
            return [self.decode(v) for v in value]
        if t is not dict:
            raise RemoteError("对面发来的数据格式不对")
        if "$ref" in value:
            return self._proxy(value)
        if len(value) != 1:
            raise RemoteError("对面发来的数据格式不对")
        ((tag, body),) = value.items()
        if tag == "$dict":
            return {self.decode(k): self.decode(v) for k, v in body}
        if tag in ("$tuple", "$set", "$frozenset"):
            items = [self.decode(v) for v in _list(body)]
            return {"$tuple": tuple, "$set": set, "$frozenset": frozenset}[tag](items)
        if tag == "$bytes":
            return base64.b64decode(str(body), validate=True)
        if tag == "$yours":
            if type(body) is not int or body not in self._exports:
                raise RemoteError("对面引用了一个不存在的对象")
            return self._exports[body]
        if tag == "$builtin":
            obj = getattr(builtins, str(body), None)
            if not isinstance(obj, type):  # 只认内置的类型：open、eval、getattr 这些函数不行
                raise RemoteError("对面引用了一个不存在的内置类型")
            return obj
        if tag == "$exc":
            return self._decode_error(body)
        raise RemoteError("对面发来的数据格式不对")

    def _proxy(self, value: dict[str, Any]) -> Any:
        ref = value["$ref"]
        if type(ref) is not int:
            raise RemoteError("对面发来的数据格式不对")
        if ref in self._proxies:
            return self._proxies[ref]
        name = str(value.get("name", "object"))[:200]
        proxy: Any
        if "exc" in value:
            bases = [getattr(builtins, str(n), None) for n in _list(value["exc"])]
            base = next((b for b in bases if isinstance(b, type) and issubclass(b, BaseException)), Exception)
            proxy = type(name.rsplit(".", 1)[-1] or "RemoteException", (base,),
                         {"__module__": str(value.get("module", ""))[:200], "__qualname__": name})
            self._stand_ins[proxy] = ref
        else:
            snapshot = self.decode(value["value"]) if "value" in value else _MISSING
            proxy = Remote._boxcode_new(self, ref, name, snapshot)
        self._proxies[ref] = proxy
        return proxy

    def _decode_error(self, body: Any) -> BaseException:
        if type(body) is not dict:
            raise RemoteError("对面发来的异常格式不对")
        message = str(body.get("message", ""))[:MAX_TEXT]
        cls = self.decode(body.get("type"))
        args = self.decode(body.get("args", []))
        if not isinstance(cls, type) or not issubclass(cls, BaseException) or not isinstance(args, list):
            return RemoteError(message)
        if not issubclass(cls, Exception):
            return RemoteError(f"被测代码抛出了 {cls.__name__}：{message}")
        exc: BaseException
        try:
            exc = cls(*args)
        except Exception:
            try:
                exc = cls.__new__(cls, *args)  # __init__ 要的参数和 args 对不上：不调 __init__，照样能被 except 抓到
            except Exception:
                return RemoteError(message)
        tb = body.get("traceback")
        if isinstance(tb, str) and tb:
            exc.add_note(f"被测代码的进程里：\n{tb[-MAX_TEXT:]}")
        return exc


def _list(value: Any) -> list[Any]:
    if type(value) is not list:
        raise RemoteError("对面发来的数据格式不对")
    return value


class Remote:
    """对面进程里的一个对象。取属性、调用、运算都转发过去；和这边的东西比较见模块说明。"""

    __slots__ = ("__weakref__", "_boxcode_channel", "_boxcode_id", "_boxcode_name", "_boxcode_value")

    @classmethod
    def _boxcode_new(cls, channel: Channel, ref: int, name: str, value: Any) -> "Remote":
        obj = object.__new__(cls)
        for attr, v in (("_boxcode_channel", channel), ("_boxcode_id", ref), ("_boxcode_name", name),
                        ("_boxcode_value", value)):
            object.__setattr__(obj, attr, v)
        return obj

    def _boxcode(self, op: str, *args: Any) -> Any:
        return object.__getattribute__(self, "_boxcode_channel").request(op, *args)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_boxcode_"):
            raise AttributeError(name)
        return self._boxcode("getattr", self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        self._boxcode("setattr", self, name, value)

    def __delattr__(self, name: str) -> None:
        self._boxcode("delattr", self, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return object.__getattribute__(self, "_boxcode_channel").request("call", self, *args, **kwargs)

    def __repr__(self) -> str:
        with contextlib.suppress(Exception):
            text = self._boxcode("repr", self)
            if isinstance(text, str):
                return text
        return f"<被测进程里的 {object.__getattribute__(self, '_boxcode_name')}>"

    def __str__(self) -> str:
        return self._boxcode("str", self)  # type: ignore[no-any-return]

    def __bool__(self) -> bool:
        value = object.__getattribute__(self, "_boxcode_value")
        return bool(value) if value is not _MISSING else self._boxcode("bool", self)

    def __hash__(self) -> int:
        value = object.__getattribute__(self, "_boxcode_value")
        return hash(value) if value is not _MISSING else self._boxcode("hash", self)

    def _boxcode_compare(self, op: str, other: Any) -> Any:
        if isinstance(other, Remote) and (object.__getattribute__(other, "_boxcode_channel")
                                          is object.__getattribute__(self, "_boxcode_channel")):
            return self._boxcode(op, self, other)  # 两边都是被测进程里的对象：交给被测代码判断
        value = object.__getattribute__(self, "_boxcode_value")
        if value is not _MISSING:
            return _COMPARISONS[op](value, other)  # 用普通数据的拷贝在这边比较
        return NotImplemented  # 不交给被测代码的 __eq__：== 落到“不是同一个对象”，<、> 抛 TypeError

    def __eq__(self, other: object) -> Any:
        return self._boxcode_compare("eq", other)

    def __ne__(self, other: object) -> Any:
        return self._boxcode_compare("ne", other)

    def __lt__(self, other: Any) -> Any:
        return self._boxcode_compare("lt", other)

    def __le__(self, other: Any) -> Any:
        return self._boxcode_compare("le", other)

    def __gt__(self, other: Any) -> Any:
        return self._boxcode_compare("gt", other)

    def __ge__(self, other: Any) -> Any:
        return self._boxcode_compare("ge", other)

    def __len__(self) -> int:
        return self._boxcode("len", self)  # type: ignore[no-any-return]

    def __iter__(self) -> Any:
        return self._boxcode("iter", self)

    def __next__(self) -> Any:
        return self._boxcode("next", self)

    def __reversed__(self) -> Any:
        return self._boxcode("reversed", self)

    def __contains__(self, item: Any) -> bool:
        value = object.__getattribute__(self, "_boxcode_value")
        if value is not _MISSING:  # 和比较一样：str、list 这些的子类按普通数据的拷贝算，不交给被测代码
            return item in value
        return self._boxcode("contains", self, item)  # type: ignore[no-any-return]

    def __getitem__(self, key: Any) -> Any:
        return self._boxcode("getitem", self, key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self._boxcode("setitem", self, key, value)

    def __delitem__(self, key: Any) -> None:
        self._boxcode("delitem", self, key)

    def __index__(self) -> int:
        return self._boxcode("index", self)  # type: ignore[no-any-return]

    def __int__(self) -> int:
        return self._boxcode("int", self)  # type: ignore[no-any-return]

    def __float__(self) -> float:
        return self._boxcode("float", self)  # type: ignore[no-any-return]

    def __format__(self, spec: str) -> str:
        return self._boxcode("format", self, spec)  # type: ignore[no-any-return]

    def __dir__(self) -> Iterable[str]:
        return self._boxcode("dir", self)  # type: ignore[no-any-return]

    def __neg__(self) -> Any:
        return self._boxcode("neg", self)

    def __pos__(self) -> Any:
        return self._boxcode("pos", self)

    def __abs__(self) -> Any:
        return self._boxcode("abs", self)

    def __invert__(self) -> Any:
        return self._boxcode("invert", self)

    def __enter__(self) -> Any:
        return self._boxcode("enter", self)

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> Any:
        return self._boxcode("exit", self, exc)

    def __instancecheck__(self, obj: Any) -> bool:
        return self._boxcode("isinstance", obj, self)  # type: ignore[no-any-return]

    def __subclasscheck__(self, cls: Any) -> bool:
        return self._boxcode("issubclass", cls, self)  # type: ignore[no-any-return]


def _arithmetic(op: str, reflected: bool) -> Callable[[Remote, Any], Any]:
    def method(self: Remote, other: Any) -> Any:
        return self._boxcode(op, other, self) if reflected else self._boxcode(op, self, other)

    return method


for _op in _ARITHMETIC:
    setattr(Remote, f"__{_op}__", _arithmetic(_op, reflected=False))
    setattr(Remote, f"__r{_op}__", _arithmetic(_op, reflected=True))


# ---- 测试进程这边：导入 editable 里的模块时换成代理 ----


class RemoteModule(types.ModuleType):
    """测试进程里看到的 editable 模块：模块自己的属性（__name__、__file__……）在这边，其他的都去被测进程里取。"""

    def __getattr__(self, name: str) -> Any:
        remote = self.__dict__.get("_boxcode_remote")
        if remote is None or (name.startswith("__") and name.endswith("__")):
            raise AttributeError(name)
        return getattr(remote, name)


class _RemoteLoader(importlib.abc.Loader):
    def __init__(self, channel: Channel, root: Path) -> None:
        self._channel, self._root = channel, root

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        return RemoteModule(spec.name)

    def exec_module(self, module: types.ModuleType) -> None:
        paths = [p for p in sys.path if _inside(self._root, p)]
        remote = self._channel.request("import", module.__name__, paths)
        module.__dict__["_boxcode_remote"] = remote
        # `from stats import *` 只看模块的 __dict__ 和 __all__
        module.__dict__["__all__"] = [n for n in self._channel.request("public_names", remote) if isinstance(n, str)]


def _inside(root: Path, path: str) -> bool:
    try:
        Path(path).resolve().relative_to(root)
    except (ValueError, OSError):
        return False
    return True


class _RemoteFinder(importlib.abc.MetaPathFinder):
    """排在 sys.meta_path 最前面：找到的模块文件在判分目录里、属于 editable，就交给被测进程。"""

    def __init__(self, channel: Channel, root: Path, editable: Sequence[str]) -> None:
        self._channel, self._root, self._editable = channel, root, tuple(editable)

    def find_spec(
        self, fullname: str, path: Sequence[str] | None, target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.origin is None or not spec.has_location:
            return None
        try:
            rel = Path(spec.origin).resolve().relative_to(self._root).as_posix()
        except (ValueError, OSError):
            return None
        if not is_editable(self._editable, rel):
            return None
        return importlib.util.spec_from_file_location(
            fullname, spec.origin, loader=_RemoteLoader(self._channel, self._root),
            submodule_search_locations=spec.submodule_search_locations)


def _fds(value: str) -> tuple[int, int]:
    rfd, wfd = (int(x) for x in value.split(","))
    for fd in (rfd, wfd):
        os.set_inheritable(fd, False)  # 测试里起的子进程拿不到
    return rfd, wfd


def install_from_env() -> Channel | None:
    """测试进程（报告插件）调用：环境变量里有被测进程的管道时，装上导入钩子。"""
    fds = os.environ.get(TESTER_FDS_ENV)
    if not fds:
        return None
    channel = Channel(*_fds(fds), OPS, tracebacks=False, exports_only=True)
    root = Path(os.environ[CHECK_DIR_ENV]).resolve()
    editable = json.loads(os.environ[EDITABLE_ENV])
    sys.meta_path.insert(0, _RemoteFinder(channel, root, [str(p) for p in editable]))
    return channel


def main() -> None:
    """被测进程：python -I -B -c "from boxcode.evals.remote import main; main()" <判分目录>。"""
    root = sys.argv[1]
    sys.path.insert(0, root)
    channel = Channel(*_fds(os.environ.pop(WORKER_FDS_ENV)), WORKER_OPS, tracebacks=True, exports_only=False)
    try:
        channel.serve()
    finally:
        sys.stdout.flush()
        os._exit(0)  # 不等被测代码自己起的线程，也不跑它注册的 atexit
