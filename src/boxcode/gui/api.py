"""桌面界面背后的接口：页面里的 JavaScript 只能调 EXPOSED 里列出的方法，每次都要带上本次窗口的 token。

为什么不把 GuiApi 整个交给 pywebview（js_api=api）：pywebview 按页面给的点号路径逐级 getattr，
`_settings.home.parent.chmod` 这种路径也能调到；窗口一旦被导航到别的页面（例如把仓库里的 HTML 拖进窗口），
那个页面也会拿到同样的接口。所以只用 window.expose 暴露 bridge_functions 生成的几个函数，
函数先核对 token（只写在我们自己的页面里），再调对应的方法。

这个模块不依赖 pywebview，可以单独测试；窗口、文件夹对话框、往页面推消息都由 app.py 传进来。
运行和评测都在后台线程里做，过程用 push 实时推给页面：
- trace：执行轨迹的每一条事件，和写进 ~/.boxcode/runs/ 的一样
- approval / approval_resolved：权限策略要问人的调用，在页面上点放行或拒绝
- run_finished、eval_progress、eval_finished

按“停止”会设置这次运行的取消信号：正在执行的命令立刻被杀掉，等着确认的调用一律拒绝，
正在进行的模型调用也不再等（见 Agent._complete），这次运行马上以 cancelled 结束。
"""

import contextlib
import json
import re
import secrets
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from boxcode.agent import Agent
from boxcode.config import Settings
from boxcode.evals import Task, TaskResult, load_tasks, run_task, save_report
from boxcode.llm.base import LLMProvider, LLMUnavailable
from boxcode.llm.factory import make_provider
from boxcode.policy import ApprovalMode, Decision, ExecutionPolicy
from boxcode.tools import Tool
from boxcode.trace import TraceRecorder, read_trace

Push = Callable[[str, dict[str, Any]], None]

# 页面传来的 id 会拼进路径，只认这两种格式
RUN_ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")
REPORT_ID = re.compile(r"\d{8}-\d{6}")
# 历史轨迹列表最多显示这么多条
MAX_RUNS = 200
SUMMARY_KEYS = ("llm_calls", "tool_calls", "prompt_tokens", "completion_tokens", "cached_tokens", "denied")
REPORT_KEYS = ("model", "tasks", "pass_rate", "injection_induced_rate", "avg_llm_calls", "total_tokens")
# 关窗口时最多等后台的运行和评测这么久，让它们写完 run_end
SHUTDOWN_WAIT_S = 10
# 页面能调的方法
EXPOSED = (
    "info", "pick_folder", "start_run", "stop_run", "answer_approval", "list_runs", "load_run",
    "list_tasks", "start_eval", "stop_eval", "list_reports", "load_report", "load_eval_trace",
)


class RunRequest(BaseModel):
    task: str
    workspace: str
    mode: ApprovalMode = ApprovalMode.WORKSPACE_WRITE
    verify: str | None = None
    allow_network: bool = False


@dataclass
class _Approval:
    done: threading.Event = field(default_factory=threading.Event)
    approved: bool = False


def _fail(error: str) -> dict[str, Any]:
    return {"ok": False, "error": error}


def run_summary(run_id: str, events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """历史列表里的一行：开始时的任务和配置，加上结束时的状态和统计。没有 run_start 的文件不算一次运行。"""
    start = next((e for e in events if e.get("event") == "run_start"), None)
    if start is None:
        return None
    end = next((e for e in reversed(events) if e.get("event") == "run_end"), None)
    return {
        "run_id": run_id, "ts": start.get("ts"), "task": start.get("task", ""), "model": start.get("model"),
        "mode": start.get("mode"), "workspace": start.get("workspace"),
        "status": end.get("status") if end else None,  # None：还在运行，或者进程中途被杀
        "summary": {k: end.get(k) for k in SUMMARY_KEYS} if end else None,
    }


def _read_report(report_dir: Path) -> dict[str, Any] | None:
    try:
        rep = json.loads((report_dir / "report.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return rep if isinstance(rep, dict) else None


class GuiApi:
    def __init__(
        self,
        settings: Settings,
        tasks_dir: Path,
        results_dir: Path,
        push: Push,
        pick_folder: Callable[[], str | None] = lambda: None,
        make_llm: Callable[[Settings], LLMProvider] = make_provider,
    ) -> None:
        self._settings = settings
        self._tasks_dir = tasks_dir
        self._results_dir = results_dir
        self._push = push
        self._pick_folder = pick_folder
        self._make_llm = make_llm
        self._lock = threading.Lock()
        self._run: threading.Thread | None = None
        self._run_stop = threading.Event()
        self._eval: threading.Thread | None = None
        self._eval_stop = threading.Event()
        self._approvals: dict[str, _Approval] = {}
        self._closed = False
        # “正在运行”看这两个标记，不看线程是否还活着：线程推完 run_finished 才退出，
        # 页面收到消息马上再点开始，那一刻线程还活着，会被误判成“已经有一个任务在运行”
        self._run_busy = False
        self._eval_busy = False

    def _send(self, kind: str, **data: Any) -> None:
        # 窗口关了就不再推：往正在关闭的窗口执行 JavaScript 可能一直卡住
        if self._closed:
            return
        with contextlib.suppress(Exception):
            self._push(kind, data)

    # ---- 配置 ----

    def info(self) -> dict[str, Any]:
        s = self._settings
        home = Path.home()

        def short(p: Path) -> str:  # 只用来显示：主目录写成 ~
            return f"~/{p.relative_to(home)}" if p.is_relative_to(home) else str(p)

        return {
            "provider": s.provider, "model": s.model, "effort": s.effort if s.provider == "anthropic" else None,
            "runs_dir": short(s.runs_dir), "tasks_dir": short(self._tasks_dir), "results_dir": short(self._results_dir),
            "cwd": str(Path.cwd()), "sandbox": "seatbelt" if sys.platform == "darwin" else None,
        }

    def pick_folder(self) -> str | None:
        return self._pick_folder()

    # ---- 发起任务 ----

    def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            req = RunRequest.model_validate(request)
        except ValidationError as e:
            return _fail(f"参数不对：{e.errors()[0]['msg']}")
        if not req.task.strip():
            return _fail("先写要 Agent 做的事")
        workspace = Path(req.workspace).expanduser()
        if not workspace.is_dir():
            return _fail(f"工作区不存在：{workspace}")
        verify = (req.verify or "").strip() or None

        with self._lock:
            if self._run_busy:
                return _fail("已经有一个任务在运行")
            try:
                llm = self._make_llm(self._settings)
            except LLMUnavailable as e:
                return _fail(str(e))
            self._run_stop = threading.Event()
            trace = TraceRecorder(self._settings.runs_dir, listener=lambda e: self._send("trace", event=e))
            try:
                agent = Agent(llm, workspace.resolve(), self._settings, ExecutionPolicy(req.mode, req.allow_network),
                              approver=self._approve, trace=trace, cancel=self._run_stop)
            except (RuntimeError, ValueError) as e:  # 不是 macOS（没有沙盒），或者工作区不安全
                return _fail(str(e))
            self._run_busy = True
            self._run = threading.Thread(target=self._do_run, args=(agent, req.task, verify), daemon=True)
            self._run.start()
        return {"ok": True, "run_id": trace.run_id}

    def _do_run(self, agent: Agent, task: str, verify: str | None) -> None:
        # Agent 自己出 bug 也会以 crashed 结束、返回结果；这里再兜一层，线程不能悄悄死掉、让页面一直显示“运行中”
        status, final = "crashed", None
        try:
            result = agent.run(task, verify_command=verify)
            status, final = result.status.value, result.final_message
        except Exception as e:
            final = f"{type(e).__name__}: {e}"
        finally:
            with self._lock:
                self._run_busy = False
        self._resolve_all(approved=False)
        self._send("run_finished", run_id=agent.trace.run_id, status=status, final_message=final,
                   summary=agent.trace.summary(), trace_path=str(agent.trace.path))

    def stop_run(self) -> None:
        with self._lock:
            self._run_stop.set()
        self._resolve_all(approved=False)

    def _approve(self, tool: Tool[Any], params: BaseModel, decision: Decision) -> bool:
        """权限策略说“要问”时，在 Agent 的线程里调用：推给页面，等用户点放行或拒绝。"""
        request_id = uuid.uuid4().hex
        approval = _Approval()
        with self._lock:
            # 和 stop_run 共用一把锁：停止之后不会再有新的提问挂起来没人回答
            if self._run_stop.is_set():
                return False
            self._approvals[request_id] = approval
        self._send("approval", id=request_id, tool=tool.name, params=params.model_dump(mode="json"),
                   reason=decision.reason)
        approval.done.wait()
        with self._lock:
            self._approvals.pop(request_id, None)
        self._send("approval_resolved", id=request_id, approved=approval.approved)
        return approval.approved

    def answer_approval(self, request_id: str, approved: bool) -> None:
        with self._lock:
            approval = self._approvals.get(request_id)
            if approval is not None and not approval.done.is_set():
                approval.approved = approved is True  # 页面传来的是 JSON："false" 这种字符串不能当成同意
                approval.done.set()

    def _resolve_all(self, approved: bool) -> None:
        with self._lock:
            for approval in self._approvals.values():
                if not approval.done.is_set():
                    approval.approved = approved
                    approval.done.set()

    # ---- 历史轨迹 ----

    def list_runs(self) -> list[dict[str, Any]]:
        runs_dir = self._settings.runs_dir
        if not runs_dir.is_dir():
            return []
        # 文件名以时间开头，倒序就是最新的在前
        paths = sorted(runs_dir.glob("*.jsonl"), reverse=True)[:MAX_RUNS]
        return [s for p in paths if (s := run_summary(p.stem, read_trace(p))) is not None]

    def load_run(self, run_id: str) -> list[dict[str, Any]]:
        if not RUN_ID.fullmatch(run_id):
            return []
        path = self._settings.runs_dir / f"{run_id}.jsonl"
        return read_trace(path) if path.is_file() else []

    # ---- 评测 ----

    def list_tasks(self) -> list[dict[str, Any]]:
        if not self._tasks_dir.is_dir():
            return []
        return [{"id": t.id, "category": t.category, "prompt": t.prompt} for t in load_tasks(self._tasks_dir)]

    def start_eval(self, task_ids: list[str]) -> dict[str, Any]:
        if not isinstance(task_ids, list) or not all(isinstance(t, str) for t in task_ids):
            return _fail("参数不对：task_ids 要是题目 id 的列表")
        with self._lock:
            if self._eval_busy:
                return _fail("已经有一轮评测在运行")
            tasks = load_tasks(self._tasks_dir, task_ids) if task_ids and self._tasks_dir.is_dir() else []
            if not tasks:
                return _fail("先选要跑的题目")
            try:
                self._make_llm(self._settings)  # 先检查一次配置，没有 key 就不开始
            except LLMUnavailable as e:
                return _fail(str(e))
            report_id, run_dir = _new_report_dir(self._results_dir)
            self._eval_stop = threading.Event()
            self._eval_busy = True
            self._eval = threading.Thread(target=self._do_eval, args=(tasks, run_dir, self._eval_stop), daemon=True)
            self._eval.start()
        return {"ok": True, "report_id": report_id, "task_ids": [t.id for t in tasks]}

    def _do_eval(self, tasks: list[Task], run_dir: Path, stop: threading.Event) -> None:
        report_id = run_dir.name
        results: list[TaskResult] = []

        def make_llm() -> LLMProvider:
            return self._make_llm(self._settings)

        def done() -> None:
            with self._lock:
                self._eval_busy = False

        try:
            for task in tasks:
                if stop.is_set():
                    break
                self._send("eval_progress", report_id=report_id, task_id=task.id, state="running")
                results.append(run_task(task, make_llm, self._settings, run_dir, cancel=stop))
                save_report(run_dir, results, self._settings.model)
                self._send("eval_progress", report_id=report_id, task_id=task.id, state="done",
                           result=asdict(results[-1]))
            rep = save_report(run_dir, results, self._settings.model)
            done()
            self._send("eval_finished", report_id=report_id, stopped=stop.is_set(), report=rep)
        except Exception as e:
            # 评测框架自己出错（复制题目失败之类）：页面上要能看到，而不是一直显示“运行中”
            done()
            self._send("eval_finished", report_id=report_id, stopped=True, error=f"{type(e).__name__}: {e}")

    def stop_eval(self) -> None:
        """当前这道题以 cancelled 结束（正在跑的命令和判分都会被杀掉，记成没通过），后面的题不再开始。"""
        self._eval_stop.set()

    def list_reports(self) -> list[dict[str, Any]]:
        if not self._results_dir.is_dir():
            return []
        return [
            {"id": d.name, **{k: rep.get(k) for k in REPORT_KEYS}}
            for d in sorted(self._results_dir.iterdir(), reverse=True)
            if REPORT_ID.fullmatch(d.name) and (rep := _read_report(d)) is not None
        ]

    def load_report(self, report_id: str) -> dict[str, Any] | None:
        return _read_report(self._results_dir / report_id) if REPORT_ID.fullmatch(report_id) else None

    def load_eval_trace(self, report_id: str, task_id: str) -> list[dict[str, Any]]:
        rep = self.load_report(report_id)
        for r in (rep or {}).get("results", []):
            if r.get("id") == task_id and r.get("trace_path"):
                # 报告里记的路径是相对评测时的当前目录；只取文件名，到这份报告自己的 runs/ 里找
                name = Path(r["trace_path"]).name
                path = self._results_dir / report_id / "runs" / name
                if RUN_ID.fullmatch(Path(name).stem) and path.is_file():
                    return read_trace(path)
        return []

    def shutdown(self, wait_s: float = SHUTDOWN_WAIT_S) -> None:
        """窗口关掉时调用：停下正在做的运行和评测（正在执行的命令会被杀掉，等着确认的调用一律拒绝），
        再等它们写完 run_end。进程退出时后台线程会被直接结束，不等的话轨迹里就没有结尾。"""
        self._closed = True
        self.stop_run()
        self.stop_eval()
        deadline = time.monotonic() + wait_s
        for thread in (self._run, self._eval):
            if thread is not None:
                thread.join(max(0.0, deadline - time.monotonic()))


def _new_report_dir(results_dir: Path) -> tuple[str, Path]:
    """评测结果目录按秒命名；同一秒里开了两轮，第二轮等到下一秒，不和第一轮混在一起。"""
    while True:
        report_id = time.strftime("%Y%m%d-%H%M%S")
        run_dir = results_dir / report_id
        try:
            run_dir.mkdir(parents=True)
        except FileExistsError:
            time.sleep(0.2)
            continue
        return report_id, run_dir


def bridge_functions(api: GuiApi, token: str) -> list[Callable[..., Any]]:
    """给 window.expose 用的函数：名字和 GuiApi 的方法一样，第一个参数必须是本次窗口的 token。"""

    def make(name: str) -> Callable[..., Any]:
        method = getattr(api, name)

        def call(given: object, *args: Any) -> Any:
            if not isinstance(given, str) or not secrets.compare_digest(given, token):
                raise PermissionError("这个页面不能调用 BoxCode 的接口")
            return method(*args)

        call.__name__ = call.__qualname__ = name
        return call

    return [make(name) for name in EXPOSED]
