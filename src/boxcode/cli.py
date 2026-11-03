"""命令行：boxcode run "任务" / boxcode eval / boxcode gui。"""

import json
import time
from functools import partial
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.prompt import Confirm
from rich.status import Status
from rich.table import Table

from boxcode.agent import Agent
from boxcode.agent import Status as RunStatus
from boxcode.config import Settings
from boxcode.llm.base import LLMProvider, LLMUnavailable
from boxcode.llm.factory import make_provider
from boxcode.policy import ApprovalMode, Decision, ExecutionPolicy
from boxcode.tools import Tool

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def provider(settings: Settings) -> LLMProvider:
    try:
        return make_provider(settings)
    except LLMUnavailable as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from e


def ask_user(status: Status, tool: Tool, params: BaseModel, decision: Decision) -> bool:
    # 转圈那一行会盖住提问（用户看到的是“思考中…”，其实程序在等输入），问的时候先停下
    status.stop()
    try:
        console.print(f"[yellow]需要确认[/]：{decision.reason}")
        console.print(f"  {tool.name} {params.model_dump_json()}")
        return Confirm.ask("放行这一次？", default=False)
    except EOFError:
        return False  # 没有可以回答的输入（例如管道已经读完），当作拒绝
    finally:
        status.start()


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="要 Agent 做的事")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w", help="工作区（代码仓库）")] = Path("."),
    mode: Annotated[ApprovalMode, typer.Option(help="权限模式")] = ApprovalMode.WORKSPACE_WRITE,
    verify: Annotated[str | None, typer.Option(help="做完后的自检命令，例如 'python -m pytest -q'")] = None,
    allow_network: Annotated[bool, typer.Option("--allow-network", help="沙盒里允许联网")] = False,
    no_sandbox: Annotated[bool, typer.Option("--dangerously-no-sandbox", help="不用沙盒执行命令")] = False,
) -> None:
    settings = Settings()
    execution = ExecutionPolicy(mode, allow_network, sandboxed=not no_sandbox)
    status = console.status("思考中…")
    agent = Agent(provider(settings), workspace.resolve(), settings, execution, approver=partial(ask_user, status))
    with status:
        result = agent.run(task, verify_command=verify)
    console.rule(f"[bold]{result.status.value}[/]")
    if result.final_message:
        console.print(result.final_message)
    console.print(f"[dim]{json.dumps(result.trace.summary(), ensure_ascii=False)}[/]")
    console.print(f"[dim]轨迹：{result.trace.path}[/]")
    # 没做完（自检失败、超出轮数、接口出错……）退出码不为 0，脚本和 CI 才能判断
    if result.status is not RunStatus.DONE:
        raise typer.Exit(1)


@app.command("eval")
def eval_cmd(
    tasks_dir: Annotated[Path, typer.Option("--tasks", help="题目目录")] = Path("evals/tasks"),
    only: Annotated[list[str] | None, typer.Option(help="只跑这几道题的 id")] = None,
    out: Annotated[Path, typer.Option(help="结果目录")] = Path("evals/results"),
) -> None:
    from boxcode.evals import TaskResult, load_tasks, run_task, save_report

    settings = Settings()
    provider(settings)  # 先检查一次配置，没有 key 就直接退出
    run_dir = out / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    results: list[TaskResult] = []

    for task in load_tasks(tasks_dir, only):
        with console.status(f"{task.id}…"):
            results.append(run_task(task, lambda: provider(settings), settings, run_dir))
        r = results[-1]
        console.print(f"{'✅' if r.passed else '❌'} {r.id}  {r.agent_status}  {r.seconds}s")
        save_report(run_dir, results, settings.model)

    rep = save_report(run_dir, results, settings.model)

    table = Table("指标", "值")
    for k in ("tasks", "pass_rate", "injection_induced_rate", "avg_llm_calls", "total_tokens"):
        table.add_row(k, str(rep[k]))
    console.print(table)
    console.print(f"[dim]报告：{run_dir / 'report.json'}[/]")


@app.command()
def gui(
    tasks_dir: Annotated[Path, typer.Option("--tasks", help="评测题目目录")] = Path("evals/tasks"),
    out: Annotated[Path, typer.Option(help="评测结果目录")] = Path("evals/results"),
    debug: Annotated[bool, typer.Option(help="允许打开网页检查器")] = False,
) -> None:
    try:
        from boxcode.gui.app import launch
    except ModuleNotFoundError as e:
        if e.name != "webview":
            raise
        console.print("[red]桌面界面需要 pywebview，先运行：uv sync --extra gui[/]")
        raise typer.Exit(1) from e
    launch(tasks_dir.resolve(), out.resolve(), debug)
