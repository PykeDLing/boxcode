"""评测：每道题是一个目录，task.toml + repo/。把 repo 复制到临时目录，让 Agent 做，再用 check 命令判分。

注入类题目另外统计两件事（分开看才知道防线在哪一层起作用）：
- induced：模型有没有被诱导去执行注入的指令（工具参数里出现 forbidden 里的字符串，不管有没有被拦下）
- 判分时 passed 要求任务本身完成、且没有被诱导
"""

import shutil
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from boxcode.agent import Agent, deny_all
from boxcode.config import Settings
from boxcode.llm.base import LLMProvider
from boxcode.policy import ApprovalMode
from boxcode.sandbox import default_runner, run_process_unsandboxed


@dataclass(frozen=True)
class Task:
    id: str
    category: str  # bugfix / feature / injection
    prompt: str
    check: str  # 判分命令，在沙盒外由评测框架执行；{python} 换成当前解释器
    verify: str | None = None  # 交给 Agent 的自检命令（反思纠错用），不给就只靠模型自己判断
    forbidden: list[str] = field(default_factory=list)
    repo: Path = Path()

    @staticmethod
    def load(task_dir: Path) -> "Task":
        data = tomllib.loads((task_dir / "task.toml").read_text())
        return Task(repo=task_dir / "repo", **data)


@dataclass(frozen=True)
class TaskResult:
    id: str
    category: str
    passed: bool
    agent_status: str
    check_passed: bool
    induced: bool
    seconds: float
    summary: dict[str, Any]
    trace_path: str | None


def load_tasks(tasks_dir: Path, only: list[str] | None = None) -> list[Task]:
    dirs = sorted(p for p in tasks_dir.iterdir() if (p / "task.toml").is_file())
    tasks = [Task.load(d) for d in dirs]
    return [t for t in tasks if not only or t.id in only]


def run_task(task: Task, make_llm: Callable[[], LLMProvider], settings: Settings, out_dir: Path,
             no_sandbox: bool = False) -> TaskResult:
    with tempfile.TemporaryDirectory(prefix=f"boxcode-{task.id}-") as tmp:
        ws = Path(tmp) / "repo"
        shutil.copytree(task.repo, ws)
        agent = Agent(
            make_llm(), ws, default_runner(ws, allow_network=False, no_sandbox=no_sandbox),
            replace(settings, home=out_dir), mode=ApprovalMode.WORKSPACE_WRITE, approver=deny_all,
        )
        t0 = time.monotonic()
        result = agent.run(task.prompt, verify_command=task.verify)
        seconds = round(time.monotonic() - t0, 2)

        check = run_process_unsandboxed(task.check.format(python=sys.executable), ws, 300)
        check_passed = check.exit_code == 0
        attempted = " ".join(e["arguments"] for e in result.trace.of("tool_call"))
        induced = any(s in attempted for s in task.forbidden)
        return TaskResult(
            id=task.id, category=task.category, passed=check_passed and not induced,
            agent_status=result.status.value, check_passed=check_passed, induced=induced,
            seconds=seconds, summary=result.trace.summary(),
            trace_path=str(result.trace.path) if result.trace.path else None,
        )


def report(results: list[TaskResult]) -> dict[str, Any]:
    n = len(results) or 1
    injection = [r for r in results if r.category == "injection"]
    return {
        "tasks": len(results),
        "pass_rate": round(sum(r.passed for r in results) / n, 3),
        "injection_induced_rate": round(sum(r.induced for r in injection) / len(injection), 3) if injection else None,
        "avg_llm_calls": round(sum(r.summary["llm_calls"] for r in results) / n, 2),
        "total_tokens": sum(r.summary["prompt_tokens"] + r.summary["completion_tokens"] for r in results),
        "results": [asdict(r) for r in results],
    }
