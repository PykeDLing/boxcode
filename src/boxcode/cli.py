"""命令行：boxcode run "任务" / boxcode eval / boxcode gui。"""

import json
import time
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
) -> None:
    from boxcode.evals import TaskResult, load_tasks, run_meta, run_task, save_report

    settings = load_settings()
    provider(settings)  # 先检查一次配置，没有 key 就直接退出
    try:
        tasks = load_tasks(tasks_dir, only)
    except (OSError, ValueError) as e:
        raise fail(f"读不了题目：{e}") from e
    if not tasks:
        raise fail(f"{tasks_dir} 里没有要跑的题目")
    run_dir = out / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    results: list[TaskResult] = []
    meta = run_meta(settings)  # 配置和提交号，写进报告
    if meta["boxcode"]["dirty"]:
        console.print("[yellow]BoxCode 的代码有没提交的改动：报告里的提交号还原不出这次跑的代码[/]")

    try:
        for attempt in range(1, repeat + 1):  # 一轮一轮地跑：中途停下时，每道题跑过的次数差不多
            for task in tasks:
                with console.status(f"{task.id}（第 {attempt}/{repeat} 轮）…"):
                    results.append(run_task(task, lambda: provider(settings), settings, run_dir, attempt=attempt))
                r = results[-1]
                console.print(f"{'✅' if r.passed else '❌'} {r.id}  {r.agent_status}  {r.seconds}s  {r.check_detail}",
                              markup=False)
                save_report(run_dir, results, meta)
    except KeyboardInterrupt:
        raise fail(f"已中断，做完的 {len(results)} 道题在 {run_dir / 'report.json'}", EXIT_INTERRUPTED) from None

    rep = save_report(run_dir, results, meta)
    table = Table("指标", "值")
    for k in ("tasks", "runs", "pass_rate", "injection_induced_rate", "avg_llm_calls", "total_tokens"):
        table.add_row(k, str(rep[k]))
    console.print(table)
    if repeat > 1:
        per_task = Table("题目", "通过", "被诱导", "平均轮数", "平均 token")
        for t in rep["per_task"]:
            per_task.add_row(t["id"], f"{t['passed']}/{t['runs']}", str(t["induced"]), str(t["avg_llm_calls"]),
                             str(t["avg_tokens"]))
        console.print(per_task)
    console.print(f"[dim]报告：{escape(str(run_dir / 'report.json'))}[/]")


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
