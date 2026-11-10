"""桌面界面背后的接口：不开窗口，直接调 GuiApi，用一个列表收页面会收到的消息。"""

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from boxcode.config import Settings
from boxcode.gui import api as gui_api
from boxcode.gui.api import EXPOSED, GuiApi, bridge_functions
from boxcode.gui.app import TEXT_SUBSTITUTIONS, disable_text_substitutions, page_html
from boxcode.llm.base import LLMProvider, LLMResponse, LLMUnavailable
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.trace import TraceRecorder, read_trace
from tests.conftest import macos_only

TASKS = Path(__file__).parent.parent / "evals" / "tasks"
WAIT_S = 60


class Page:
    """假页面：记下推过来的每条消息；on 里可以挂回调，模拟用户点按钮。"""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict[str, Any]]] = []
        self.on: dict[str, Any] = {}
        self.finished = threading.Event()

    def push(self, kind: str, data: dict[str, Any]) -> None:
        self.messages.append((kind, data))
        if kind in self.on:
            self.on[kind](data)
        if kind in ("run_finished", "eval_finished"):
            self.finished.set()

    def of(self, kind: str) -> list[dict[str, Any]]:
        return [d for k, d in self.messages if k == kind]


def make_api(settings: Settings, tmp_path: Path, page: Page, script: list[LLMResponse] | None = None) -> GuiApi:
    def make_llm(_: Settings) -> LLMProvider:
        return ScriptedProvider(list(script or []))

    return GuiApi(settings, TASKS, tmp_path / "results", page.push, make_llm=make_llm)


def test_page_html_inlines_assets_with_fresh_nonce() -> None:
    html = page_html("tok-123")
    assert "{{" not in html and "/*{{" not in html
    assert 'data-token="tok-123"' in html and "base-uri 'none'" in html and "form-action 'none'" in html
    nonces = set(re.findall(r"nonce-([\w-]+)'", html)) | set(re.findall(r'<script nonce="([\w-]+)"', html))
    assert len(nonces) == 1  # CSP 和脚本标签用的是同一个
    assert "default-src 'none'" in html and "window.boxcode" in html and "--accent" in html
    assert nonces.isdisjoint(re.findall(r"nonce-([\w-]+)'", page_html()))  # 每次打开窗口都换


def test_text_fields_not_autocorrected() -> None:
    # 任务和自检命令里常有 shell 命令：自动纠正、自动大写会把它改坏
    html = page_html()
    fields = re.findall(r"<(?:input|textarea)\b[^>]*>", html)
    text_fields = [f for f in fields if 'type="checkbox"' not in f]
    assert len(text_fields) == 4
    assert all('autocorrect="off"' in f and 'autocapitalize="off"' in f for f in text_fields)


@macos_only
def test_smart_quotes_disabled_only_for_this_process() -> None:
    # 系统默认开着“智能引号和破折号”：' " -- 会被换成 ‘’ “” —，命令就坏了
    from Foundation import NSBundle, NSUserDefaults  # type: ignore[import-untyped]

    disable_text_substitutions()
    defaults = NSUserDefaults.standardUserDefaults()
    assert all(defaults.objectForKey_(k) is not None and not defaults.boolForKey_(k) for k in TEXT_SUBSTITUTIONS)
    # 只登记在这个进程的内存里，不改用户的偏好设置
    bundle = NSBundle.mainBundle().bundleIdentifier()
    saved = defaults.persistentDomainForName_(bundle) if bundle else None
    assert not any(k in (saved or {}) for k in TEXT_SUBSTITUTIONS)


def test_trace_listener_and_read_back(tmp_path: Path) -> None:
    seen: list[str] = []
    trace = TraceRecorder(tmp_path, listener=lambda e: seen.append(e["event"]))
    trace.emit("run_start", task="x")
    trace.emit("run_end", status="done")
    assert seen == ["run_start", "run_end"]
    assert trace.path is not None
    with trace.path.open("a") as f:
        f.write('{"event": "llm_ca')  # 进程中途被杀，最后一行只写了一半
    assert [e["event"] for e in read_trace(trace.path)] == ["run_start", "run_end"]


def test_history_lists_runs_newest_first(settings: Settings, tmp_path: Path) -> None:
    old = TraceRecorder(settings.runs_dir)
    old.run_id, old.path = "20260101-000000-aaaaaa", settings.runs_dir / "20260101-000000-aaaaaa.jsonl"
    old.emit("run_start", task="old task", model="m", mode="workspace-write", workspace="/w")
    old.emit("run_end", status="done", **old.summary())
    new = TraceRecorder(settings.runs_dir)
    new.emit("run_start", task="still running", model="m", mode="full-auto", workspace="/w")
    (settings.runs_dir / "20250101-000000-bbbbbb.jsonl").write_text('{"event": "llm_call"}\n')  # 没有 run_start

    api = make_api(settings, tmp_path, Page())
    runs = api.list_runs()
    assert [r["task"] for r in runs] == ["still running", "old task"]
    assert runs[0]["status"] is None and runs[1]["status"] == "done"
    assert runs[1]["summary"]["llm_calls"] == 0
    assert [e["event"] for e in api.load_run(old.run_id)] == ["run_start", "run_end"]


@pytest.mark.parametrize("bad", ["../../etc/passwd", "20260101-000000-aaaaaa/../x", "", "x.jsonl"])
def test_load_run_rejects_paths(settings: Settings, tmp_path: Path, bad: str) -> None:
    # 页面传来的 id 会拼进路径
    assert make_api(settings, tmp_path, Page()).load_run(bad) == []


def test_start_run_validates_before_starting(settings: Settings, tmp_path: Path, workspace: Path) -> None:
    api = make_api(settings, tmp_path, Page())
    assert "工作区不存在" in api.start_run({"task": "x", "workspace": str(tmp_path / "missing")})["error"]
    assert "先写" in api.start_run({"task": "  ", "workspace": str(workspace)})["error"]
    assert "参数不对" in api.start_run({"task": "x", "workspace": str(workspace), "mode": "yolo"})["error"]

    def no_key(_: Settings) -> LLMProvider:
        raise LLMUnavailable("没有配置 API key")

    api = GuiApi(settings, TASKS, tmp_path / "results", Page().push, make_llm=no_key)
    assert api.start_run({"task": "x", "workspace": str(workspace)}) == {"ok": False, "error": "没有配置 API key"}
    assert api.start_eval(["001-fix-moving-average"])["error"] == "没有配置 API key"


@macos_only
def test_run_streams_trace_then_finishes(settings: Settings, tmp_path: Path, workspace: Path) -> None:
    (workspace / "app.py").write_text("value = 1\n")
    page = Page()
    api = make_api(settings, tmp_path, page, [
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 1", new_string="value = 3")]),
        LLMResponse("Changed value to 3."),
    ])
    res = api.start_run({"task": "set value to 3", "workspace": str(workspace), "verify": "grep -q 'value = 3' app.py"})
    assert res["ok"]
    assert page.finished.wait(WAIT_S)

    events = [d["event"]["event"] for d in page.of("trace")]
    assert events == ["run_start", "repo_map", "llm_call", "tool_call", "llm_call", "verify", "run_end"]
    finished = page.of("run_finished")[0]
    assert finished["status"] == "done" and finished["run_id"] == res["run_id"]
    assert finished["final_message"] == "Changed value to 3."
    json.dumps(page.messages)  # 推给页面的消息都要能变成 JSON
    assert api.list_runs()[0]["run_id"] == res["run_id"]  # 历史轨迹里马上就有


@macos_only
@pytest.mark.parametrize("approved", [True, False])
def test_risky_command_waits_for_page(settings: Settings, tmp_path: Path, workspace: Path, approved: bool) -> None:
    page = Page()
    api = make_api(settings, tmp_path, page, [
        LLMResponse(None, [call("run_command", command="echo curl")]),  # 命中“联网或远程访问”，要问
        LLMResponse("ok"),
    ])
    page.on["approval"] = lambda d: api.answer_approval(d["id"], approved)
    assert api.start_run({"task": "x", "workspace": str(workspace)})["ok"]
    assert page.finished.wait(WAIT_S)

    asked = page.of("approval")[0]
    assert asked["tool"] == "run_command" and asked["params"]["command"] == "echo curl"
    assert "高风险命令" in asked["reason"]
    assert page.of("approval_resolved") == [{"id": asked["id"], "approved": approved}]
    tool = next(d["event"] for d in page.of("trace") if d["event"]["event"] == "tool_call")
    assert tool["decision"] == ("allow" if approved else "deny")
    assert ("用户同意" if approved else "用户拒绝") in tool["reason"]


@macos_only
def test_stop_denies_pending_approval_and_ends_run(settings: Settings, tmp_path: Path, workspace: Path) -> None:
    page = Page()
    api = make_api(settings, tmp_path, page, [
        LLMResponse(None, [call("run_command", command="echo curl")]),
        LLMResponse("should not be reached"),
    ])
    page.on["approval"] = lambda _: api.stop_run()  # 有提问挂着的时候按了停止
    assert api.start_run({"task": "x", "workspace": str(workspace)})["ok"]
    assert page.finished.wait(WAIT_S)

    assert page.of("approval_resolved")[0]["approved"] is False
    finished = page.of("run_finished")[0]
    assert finished["status"] == "cancelled" and "停止" in finished["final_message"]
    # 线程已经结束、没有卡在等待上：马上能开下一次
    page.finished.clear()
    assert api.start_run({"task": "again", "workspace": str(workspace)})["ok"]
    assert page.finished.wait(WAIT_S)


@macos_only
def test_stop_during_model_call_finishes_run(settings: Settings, tmp_path: Path, workspace: Path) -> None:
    # 以前按停止要等正在进行的模型调用返回，页面一直显示“运行中”
    entered, release = threading.Event(), threading.Event()

    class Hanging:
        name = "hanging"

        def complete(self, messages: Any, tools: Any, *, cancel: object = None) -> LLMResponse:
            entered.set()
            release.wait(WAIT_S)
            return LLMResponse("done")

    page = Page()
    api = GuiApi(settings, TASKS, tmp_path / "results", page.push, make_llm=lambda _: Hanging())
    try:
        assert api.start_run({"task": "x", "workspace": str(workspace)})["ok"]
        assert entered.wait(WAIT_S)
        t0 = time.monotonic()
        api.stop_run()
        assert page.finished.wait(5) and time.monotonic() - t0 < 3
        assert page.of("run_finished")[0]["status"] == "cancelled"
        assert api.start_run({"task": "y", "workspace": str(workspace)})["ok"]  # 马上就能开始下一个任务
    finally:
        release.set()
        api.shutdown()


@macos_only
def test_one_run_at_a_time(settings: Settings, tmp_path: Path, workspace: Path) -> None:
    release = threading.Event()

    class Slow:
        name = "slow"

        def complete(self, messages: Any, tools: Any, *, cancel: object = None) -> LLMResponse:
            release.wait(WAIT_S)
            return LLMResponse("done")

    page = Page()
    api = GuiApi(settings, TASKS, tmp_path / "results", page.push, make_llm=lambda _: Slow())
    request = {"task": "x", "workspace": str(workspace)}
    assert api.start_run(request)["ok"]
    assert api.start_run(request) == {"ok": False, "error": "已经有一个任务在运行"}
    release.set()
    assert page.finished.wait(WAIT_S)


def test_reports_and_eval_traces(settings: Settings, tmp_path: Path) -> None:
    results = tmp_path / "results"
    report_dir = results / "20261104-000413"
    (report_dir / "runs").mkdir(parents=True)
    trace = TraceRecorder(report_dir / "runs")
    trace.emit("run_start", task="t")
    # 报告里的路径是相对评测时的当前目录，不一定能直接打开
    assert trace.path is not None
    trace_path = f"evals/results/whatever/runs/{trace.path.name}"
    report = {"model": "m", "tasks": 1, "pass_rate": 1.0, "injection_induced_rate": None, "avg_llm_calls": 1.0,
              "total_tokens": 10, "results": [{"id": "001-x", "trace_path": trace_path}]}
    (report_dir / "report.json").write_text(json.dumps(report))
    (results / "not-a-report").mkdir()
    (results / "20250101-000000").mkdir()  # 没有 report.json

    api = make_api(settings, tmp_path, Page())
    assert api.list_reports() == [{"id": "20261104-000413", **{k: v for k, v in report.items() if k != "results"}}]
    assert api.load_report("20261104-000413") == report
    assert api.load_report("../20261104-000413") is None
    assert [e["event"] for e in api.load_eval_trace("20261104-000413", "001-x")] == ["run_start"]
    assert api.load_eval_trace("20261104-000413", "no-such-task") == []
    assert api.start_eval([])["error"] == "先选要跑的题目"
    assert api.list_tasks()[0]["id"] == "001-fix-moving-average"


@macos_only
def test_eval_reports_progress(settings: Settings, tmp_path: Path) -> None:
    page = Page()
    fix = call("edit_file", path="stats.py", old_string="range(len(values) - window)",
               new_string="range(len(values) - window + 1)")
    api = make_api(settings, tmp_path, page, [LLMResponse(None, [fix]), LLMResponse("fixed")])
    res = api.start_eval(["001-fix-moving-average"])
    assert res["ok"] and res["task_ids"] == ["001-fix-moving-average"]
    assert page.finished.wait(WAIT_S)

    assert [d["state"] for d in page.of("eval_progress")] == ["running", "done"]
    finished = page.of("eval_finished")[0]
    assert finished["report_id"] == res["report_id"] and not finished["stopped"]
    assert finished["report"]["pass_rate"] == 1.0
    # 报告里记着这一轮的配置和代码版本
    assert finished["report"]["config"]["planning"] is True and "commit" in finished["report"]["boxcode"]
    assert api.list_reports()[0]["id"] == res["report_id"]
    events = api.load_eval_trace(res["report_id"], "001-fix-moving-average")
    assert events[0]["event"] == "run_start" and events[-1]["event"] == "run_end"


def test_bridge_requires_token_and_hides_internals(settings: Settings, tmp_path: Path) -> None:
    # pywebview 按点号路径逐级 getattr：把 GuiApi 整个交出去，页面就能调 _resolve_all、_settings.home.parent.chmod
    api = make_api(settings, tmp_path, Page())
    funcs = {f.__name__: f for f in bridge_functions(api, "secret-token")}
    assert set(funcs) == set(EXPOSED) and not any(name.startswith("_") for name in funcs)
    assert funcs["list_tasks"]("secret-token")[0]["id"] == "001-fix-moving-average"
    # 窗口被导航到别的页面时，那个页面也拿得到接口，但没有 token
    for bad in ("wrong", None, ["secret-token"]):
        with pytest.raises(PermissionError):
            funcs["start_run"](bad, {"task": "x", "workspace": "/"})
    assert all(hasattr(api, name) and callable(getattr(api, name)) for name in EXPOSED)


def test_page_cannot_smuggle_approval(settings: Settings, tmp_path: Path) -> None:
    api = make_api(settings, tmp_path, Page())
    approval = gui_api._Approval()
    api._approvals["r1"] = approval
    api.answer_approval("r1", "false")  # type: ignore[arg-type]  # JSON 里来的字符串不能当成同意
    assert approval.done.is_set() and approval.approved is False
    assert api.start_eval("001")["error"].startswith("参数不对")  # type: ignore[arg-type]


def test_start_run_refuses_unsafe_workspace(settings: Settings, tmp_path: Path) -> None:
    res = make_api(settings, tmp_path, Page(), [LLMResponse("ok")]).start_run(
        {"task": "x", "workspace": str(Path.home())})
    assert not res["ok"] and "主目录" in res["error"]


@macos_only
def test_shutdown_waits_for_run_end(settings: Settings, tmp_path: Path, workspace: Path) -> None:
    # 关窗口时正在执行的命令要被杀掉，轨迹里要有 run_end；以前进程直接退出，历史里一直显示“未结束”
    page = Page()
    api = make_api(settings, tmp_path, page, [LLMResponse(None, [call("run_command", command="sleep 30")])])
    res = api.start_run({"task": "x", "workspace": str(workspace), "mode": "full-auto"})
    assert res["ok"]
    deadline = time.monotonic() + WAIT_S
    while not any(d["event"]["event"] == "llm_call" for d in page.of("trace")) and time.monotonic() < deadline:
        time.sleep(0.05)
    t0 = time.monotonic()
    api.shutdown()
    assert time.monotonic() - t0 < 5
    events = api.load_run(res["run_id"])
    assert events[-1]["event"] == "run_end" and events[-1]["status"] == "cancelled"
    assert not page.of("run_finished")  # 窗口已经关了，不再往页面推


def test_trace_with_line_separator_reads_back(tmp_path: Path) -> None:
    # U+2028 在 JSON 里是原样写的，按 splitlines 读会把这条事件切成两半、悄悄丢掉
    trace = TraceRecorder(tmp_path)
    trace.emit("plan_update", steps=[{"step": "a b", "status": "pending"}])
    assert trace.path is not None
    assert read_trace(trace.path)[0]["steps"][0]["step"] == "a b"


def test_trace_with_lone_surrogate_does_not_raise(tmp_path: Path) -> None:
    # 模型给的参数里可能有单独的代理字符，写轨迹不能让运行崩掉，事件也要留下
    trace = TraceRecorder(tmp_path)
    trace.emit("tool_call", arguments="bad \udc80 text")
    assert trace.write_error is None and trace.path is not None
    assert read_trace(trace.path)[0]["arguments"] == "bad \udc80 text"
