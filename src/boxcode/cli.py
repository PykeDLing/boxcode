"""命令行：boxcode run "任务" / boxcode eval / boxcode compare / boxcode gui。"""

import json
from functools import partial
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.status import Status
from rich.table import Table

from boxcode import __version__
from boxcode.agent import Agent
from boxcode.agent import Status as RunStatus
from boxcode.config import ConfigError, Settings
from boxcode.llm.base import LLMProvider, LLMUnavailable
from boxcode.llm.factory import make_provider
from boxcode.policy import ApprovalMode, Decision, ExecutionPolicy, UnsafeWorkspace
from boxcode.tools import Tool

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

# 退出码：0 做完；1 没做完（自检失败、出错……）；2 配置或参数不对；130 被 Ctrl-C 打断
EXIT_NOT_DONE = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


def fail(message: str, code: int = EXIT_USAGE) -> typer.Exit:
    console.print(f"[red]{escape(message)}[/]")  # 消息里常有路径、[Errno 13] 这种方括号，不能当成样式标记
    return typer.Exit(code)


def load_settings() -> Settings:
    try:
        return Settings.from_env()
    except ConfigError as e:
        raise fail(str(e)) from e


def provider(settings: Settings) -> LLMProvider:
    try:
        return make_provider(settings)
    except LLMUnavailable as e:
        raise fail(str(e)) from e


def ask_user(status: Status, tool: Tool[Any], params: BaseModel, decision: Decision) -> bool:
    # 转圈那一行会盖住提问（用户看到的是“思考中…”，其实程序在等输入），问的时候先停下
    status.stop()
    try:
        console.print(f"[yellow]需要确认[/]：{escape(decision.reason)}")
        console.print(f"  {tool.name} {params.model_dump_json()}", markup=False)
        return Confirm.ask("放行这一次？", default=False)
    except EOFError:
        return False  # 没有可以回答的输入（例如管道已经读完），当作拒绝
    finally:
        status.start()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"boxcode {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[bool, typer.Option("--version", callback=version_callback, is_eager=True,
                                          help="显示版本号")] = False,
) -> None:
    """每条命令都在 macOS Seatbelt 沙盒里执行的编程 Agent。"""


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="要 Agent 做的事")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w", help="工作区（代码仓库）")] = Path(),
    mode: Annotated[ApprovalMode, typer.Option(help="权限模式")] = ApprovalMode.WORKSPACE_WRITE,
    verify: Annotated[str | None, typer.Option(help="做完后的自检命令，例如 'python -m pytest -q'")] = None,
    allow_network: Annotated[bool, typer.Option("--allow-network", help="沙盒里允许联网")] = False,
    no_sandbox: Annotated[bool, typer.Option("--dangerously-no-sandbox", help="不用沙盒执行命令")] = False,
) -> None:
    settings = load_settings()
    if not workspace.is_dir():
        raise fail(f"工作区不存在：{workspace}")
    execution = ExecutionPolicy(mode, allow_network, sandboxed=not no_sandbox)
    status = console.status("思考中…")
    try:
        agent = Agent(provider(settings), workspace.resolve(), settings, execution, approver=partial(ask_user, status))
    except (UnsafeWorkspace, RuntimeError) as e:  # 工作区不安全，或者不是 macOS（没有沙盒）
        raise fail(str(e)) from e
    try:
        with status:
            result = agent.run(task, verify_command=verify)
    except KeyboardInterrupt:
        # 正在跑的命令已经整组杀掉，轨迹里记了 cancelled
        raise fail(f"已中断。轨迹：{agent.trace.path}", EXIT_INTERRUPTED) from None
    console.rule(f"[bold]{result.status.value}[/]")
    if result.final_message:
        console.print(result.final_message, markup=False)
    console.print(f"[dim]{escape(json.dumps(result.trace.summary(), ensure_ascii=False))}[/]")
    console.print(f"[dim]轨迹：{escape(str(result.trace.path))}[/]")
    if result.trace.write_error:
        console.print(f"[yellow]轨迹没能完整写入：{escape(result.trace.write_error)}[/]")
    # 没做完（自检失败、超出轮数、接口出错……）退出码不为 0，脚本和 CI 才能判断
    if result.status is not RunStatus.DONE:
        raise typer.Exit(EXIT_NOT_DONE)


@app.command("eval")
def eval_cmd(
    tasks_dir: Annotated[Path, typer.Option("--tasks", help="题目目录")] = Path("evals/tasks"),
    only: Annotated[list[str] | None, typer.Option(help="只跑这几道题的 id")] = None,
    out: Annotated[Path, typer.Option(help="结果目录")] = Path("evals/results"),
    repeat: Annotated[int, typer.Option(min=1, help="每道题跑几次：模型的输出有随机性，只跑一次说明不了什么")] = 1,
    jobs: Annotated[int, typer.Option("--jobs", "-j", min=1,
                                      help="同时跑几次：各用各的工作区和沙盒，太多会撞上模型接口的限流")] = 1,
) -> None:
    from boxcode.evals import LABELS, Cause, Task, TaskResult, load_tasks, new_run_dir, result_id, run_eval, run_meta

    settings = load_settings()
    provider(settings)  # 先检查一次配置，没有 key 就直接退出
    try:
        tasks = load_tasks(tasks_dir, only)
    except (OSError, ValueError) as e:
        raise fail(f"读不了题目：{e}") from e
    if not tasks:
        raise fail(f"{tasks_dir} 里没有要跑的题目")
    run_dir = new_run_dir(out)
    meta = run_meta(settings)  # 配置和提交号，写进报告
    if meta["boxcode"]["dirty"]:
        console.print("[yellow]BoxCode 的代码有没提交的改动：报告里的提交号还原不出这次跑的代码[/]")
    status = console.status("准备中…")
    total = len(tasks) * repeat
    running: list[str] = []  # 正在跑的每一次；run_eval 保证两个回调不会同时被调用
    done = 0

    def show() -> None:
        status.update(f"{'、'.join(running)}（已完成 {done}/{total}）…")

    def on_start(task: Task, attempt: int) -> None:
        running.append(result_id(task.id, attempt))
        show()

    def on_result(r: TaskResult) -> None:
        nonlocal done
        done += 1
        running.remove(r.id)
        show()
        console.print(f"{'✅' if r.passed else '❌'} {r.id}  {r.agent_status}  {r.seconds}s  {r.check_detail}",
                      markup=False)
        if r.failure:  # 没通过的原因和依据（失败归因）
            console.print(f"   └ {LABELS[Cause(r.failure)]}：{r.failure_detail}", markup=False)

    try:
        with status:
            rep = run_eval(tasks, lambda: provider(settings), settings, run_dir, repeat=repeat, jobs=jobs, meta=meta,
                           on_start=on_start, on_result=on_result)
    except KeyboardInterrupt:
        raise fail(f"已中断，做完的 {done} 次在 {run_dir / 'report.json'}", EXIT_INTERRUPTED) from None

    table = Table("指标", "值")
    for k in ("tasks", "runs", "pass_rate", "injection_induced_rate", "avg_llm_calls", "total_tokens"):
        table.add_row(k, str(rep[k]))
    console.print(table)
    if rep["failures"]:
        failures = Table("没通过的原因", "次数")
        for cause, count in rep["failures"].items():
            failures.add_row(LABELS[Cause(cause)], str(count))
        console.print(failures)
    if rep["interrupted_runs"]:
        console.print(f"[yellow]有 {rep['interrupted_runs']} 次运行因为模型接口出错或被停止没有跑完，"
                      "通过率里照常算；要比较的话把这几次重跑[/]")
    if repeat > 1:
        per_task = Table("题目", "通过", "被诱导", "平均轮数", "平均 token")
        for t in rep["per_task"]:
            per_task.add_row(t["id"], f"{t['passed']}/{t['runs']}", str(t["induced"]), str(t["avg_llm_calls"]),
                             str(t["avg_tokens"]))
        console.print(per_task)
    console.print(f"[dim]报告：{escape(str(run_dir / 'report.json'))}[/]")


def _cause_label(cause: str) -> str:
    from boxcode.evals import LABELS, Cause

    try:
        return LABELS[Cause(cause)]
    except ValueError:  # 比这份代码新的报告里的原因
        return cause


def _signed(value: float, digits: int = 2) -> str:
    return f"{value:+.{digits}f}".rstrip("0").rstrip(".") if value else "0"


@app.command("compare")
def compare_cmd(
    a: Annotated[str, typer.Argument(help="基准那一轮：结果目录下的名字（例如 20261111-133446），或者报告的路径")],
    b: Annotated[str, typer.Argument(help="换了配置的那一轮")],
    out: Annotated[Path, typer.Option(help="结果目录")] = Path("evals/results"),
) -> None:
    """对比两轮评测：配置差在哪、指标差多少、通过率的差别是不是可能只是随机波动。"""
    from boxcode.evals import compare, describe_p, load_report

    def path_of(name: str) -> Path:
        return Path(name) if Path(name).exists() else out / name

    try:
        report_a, report_b = load_report(path_of(a)), load_report(path_of(b))
        result = compare(report_a, report_b)
    except ValueError as e:
        raise fail(str(e)) from e
    ta, tb = result.total_a, result.total_b
    for name, arg, rep, side in (("A", a, report_a, ta), ("B", b, report_b, tb)):
        console.print(f"{name}：{arg}  {rep.get('model') or '（没记模型）'}  {side.runs} 次", markup=False)

    if result.config_diff:
        config = Table("不一样的配置", "A", "B")
        for key, value_a, value_b in result.config_diff:
            config.add_row(key, *("（没记）" if v is None else escape(json.dumps(v, ensure_ascii=False))
                                  for v in (value_a, value_b)))
        console.print(config)

    def share(yes: int, total: int) -> str:
        return f"{yes}/{total}（{yes / total:.0%}）" if total else "—"

    metrics = Table("指标", "A", "B", "B − A")
    metrics.add_row("通过", share(ta.passed, ta.runs), share(tb.passed, tb.runs),
                    f"{_signed((tb.pass_rate - ta.pass_rate) * 100, 1)} 个百分点")
    if ta.injection_runs or tb.injection_runs:
        metrics.add_row("注入题里被诱导", share(ta.induced, ta.injection_runs),
                        share(tb.induced, tb.injection_runs), "")
    metrics.add_row("平均模型调用", str(ta.avg_llm_calls), str(tb.avg_llm_calls),
                    _signed(tb.avg_llm_calls - ta.avg_llm_calls))
    metrics.add_row("平均 token", str(ta.avg_tokens), str(tb.avg_tokens), _signed(tb.avg_tokens - ta.avg_tokens))
    metrics.add_row("平均耗时（秒）", str(ta.avg_seconds), str(tb.avg_seconds),
                    _signed(tb.avg_seconds - ta.avg_seconds, 1))
    if ta.avg_fix_rounds is not None and tb.avg_fix_rounds is not None:
        metrics.add_row("平均修正轮数", str(ta.avg_fix_rounds), str(tb.avg_fix_rounds),
                        _signed(tb.avg_fix_rounds - ta.avg_fix_rounds))
    if ta.interrupted or tb.interrupted:
        metrics.add_row("没跑完", str(ta.interrupted), str(tb.interrupted), "")
    console.print(metrics)

    causes = dict.fromkeys([*ta.failures, *tb.failures])
    if causes:
        failures = Table("没通过的原因", "A", "B")
        for cause in causes:
            failures.add_row(_cause_label(cause), str(ta.failures.get(cause, 0)), str(tb.failures.get(cause, 0)))
        console.print(failures)

    if len(result.per_task) > 1:
        # 每格写成“A → B”：一格一列的话 80 列的终端放不下，题目的名字会被截掉
        per_task = Table(caption="每格是 A → B；调用和 token 是每次运行的平均", caption_justify="left")
        per_task.add_column("题目", no_wrap=True)
        for header in ("通过", "模型调用", "token"):
            per_task.add_column(header)
        for row in result.per_task:
            differs = row.a.pass_rate != row.b.pass_rate  # 通过情况不一样的题标出来
            per_task.add_row(row.id, f"{row.a.passed}/{row.a.runs} → {row.b.passed}/{row.b.runs}",
                             f"{row.a.avg_llm_calls} → {row.b.avg_llm_calls}",
                             f"{row.a.avg_tokens} → {row.b.avg_tokens}", style="yellow" if differs else None)
        console.print(per_task)

    console.print(f"通过率的差别：{describe_p(result.pass_p)}", markup=False)
    if result.induced_p is not None:
        console.print(f"诱导率的差别：{describe_p(result.induced_p)}", markup=False)
    for note in result.notes:
        console.print(f"[yellow]注意[/]：{escape(note)}")


@app.command()
def gui(
    tasks_dir: Annotated[Path, typer.Option("--tasks", help="评测题目目录")] = Path("evals/tasks"),
    out: Annotated[Path, typer.Option(help="评测结果目录")] = Path("evals/results"),
    debug: Annotated[bool, typer.Option(help="允许打开网页检查器")] = False,
) -> None:
    settings = load_settings()
    try:
        from boxcode.gui.app import launch
    except ModuleNotFoundError as e:
        if e.name != "webview":
            raise
        raise fail("桌面界面需要 pywebview，先运行：uv sync --extra gui", EXIT_NOT_DONE) from e
    launch(settings, tasks_dir.resolve(), out.resolve(), debug)
