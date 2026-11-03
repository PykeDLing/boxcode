"""评测框架自测：用剧本模型做 001 号题，确认复制、执行、判分、诱导统计都对。"""

from pathlib import Path

from boxcode.config import Settings
from boxcode.evals import load_tasks, report, run_task
from boxcode.llm.base import LLMResponse
from boxcode.llm.scripted import ScriptedProvider, call
from tests.conftest import macos_only

TASKS = Path(__file__).parent.parent / "evals" / "tasks"


def test_all_tasks_load() -> None:
    tasks = load_tasks(TASKS)
    assert {t.category for t in tasks} == {"bugfix", "feature", "injection"}
    assert all((t.repo / "tests").is_dir() for t in tasks)


@macos_only
def test_scripted_fix_passes(settings: Settings, tmp_path: Path) -> None:
    task = load_tasks(TASKS, only=["001-fix-moving-average"])[0]
    fix = call("edit_file", path="stats.py", old_string="range(len(values) - window)",
               new_string="range(len(values) - window + 1)")
    result = run_task(task, lambda: ScriptedProvider([LLMResponse(None, [fix]), LLMResponse("fixed")]),
                      settings, tmp_path / "out")
    assert result.passed and result.check_passed and not result.induced
    assert (task.repo / "stats.py").read_text().count("window + 1") == 0  # 原题没被改


@macos_only
def test_injection_counted_even_when_blocked(settings: Settings, tmp_path: Path) -> None:
    task = load_tasks(TASKS, only=["101-injection-readme"])[0]
    fooled = call("run_command", command="cat ~/.ssh/id_rsa")
    result = run_task(task, lambda: ScriptedProvider([LLMResponse(None, [fooled]), LLMResponse("done")]),
                      settings, tmp_path / "out")
    assert result.induced and not result.passed
    assert report([result])["injection_induced_rate"] == 1.0
