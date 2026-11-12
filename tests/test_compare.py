"""对比两份评测报告：配置差在哪、指标差多少、差别是不是可能只是随机波动。"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from boxcode import cli
from boxcode.config import Settings
from boxcode.evals import LABELS, Cause, TaskResult, compare, describe_p, load_report, run_meta, save_report
from boxcode.evals.compare import MIN_RUNS, fisher_exact
from boxcode.evals.runner import CodeVersion

COMMIT = "1" * 40


def result(result_id: str, passed: bool = True, *, calls: int = 4, tokens: int = 1000, **fields: Any) -> TaskResult:
    made = TaskResult(id=result_id, category="bugfix", passed=passed, agent_status="done", check_passed=passed,
                      check_detail="", induced=False, seconds=10.0, trace_path=None,
                      summary={"llm_calls": calls, "prompt_tokens": tokens, "completion_tokens": 0},
                      failure=None if passed else "verify_failed")
    return replace(made, **fields)


def saved(run_dir: Path, results: list[TaskResult], settings: Settings | None = None, *, commit: str = COMMIT,
          dirty: bool = False, **extra: Any) -> dict[str, Any]:
    """用评测自己的函数写报告、再读回来：写的和读的格式对不上时这里的测试会发现。"""
    run_dir.mkdir(parents=True)
    save_report(run_dir, results, {**run_meta(settings or Settings(), CodeVersion(commit, dirty)), **extra})
    return load_report(run_dir)


def three(task: str, passed: int, **fields: Any) -> list[TaskResult]:
    """一道题跑 3 次，前 passed 次通过。"""
    return [result(task if n == 1 else f"{task}#{n}", n <= passed, **fields) for n in (1, 2, 3)]


@pytest.mark.parametrize(("table", "p"), [
    ((1, 9, 11, 3), 0.002759),  # 教科书上的例子
    ((3, 0, 0, 3), 0.1),  # 一道题 3 次全过对 3 次全不过：也只有 0.1，3 次分不出差别
    ((9, 0, 0, 9), 2 / 48620),
    ((2, 1, 2, 1), 1.0),
    ((5, 0, 5, 0), 1.0),  # 两边都全过
    ((0, 0, 3, 1), 1.0),  # 有一边一次都没有
])
def test_fisher_exact(table: tuple[int, int, int, int], p: float) -> None:
    assert fisher_exact(*table) == pytest.approx(p, rel=1e-3)
    a_yes, a_no, b_yes, b_no = table
    assert fisher_exact(b_yes, b_no, a_yes, a_no) == pytest.approx(p, rel=1e-3)  # 换一下两边，结果一样


def test_one_switch_changed(tmp_path: Path) -> None:
    # 对比实验的样子：同一份代码、同一批题，只关掉反思纠错
    a = saved(tmp_path / "a", [*three("001", 3, fix_rounds=1), *three("002", 3)])
    b = saved(tmp_path / "b", [*three("001", 0), *three("002", 3, calls=6, tokens=3000)],
              Settings(max_fix_rounds=0))
    c = compare(a, b)
    assert c.config_diff == [("max_fix_rounds", 2, 0)]
    assert (c.total_a.passed, c.total_a.runs, c.total_b.passed, c.total_b.runs) == (6, 6, 3, 6)
    assert c.total_a.pass_rate == 1.0 and c.total_b.pass_rate == 0.5
    assert (c.total_a.avg_fix_rounds, c.total_b.avg_fix_rounds) == (0.5, 0.0)
    assert (c.total_a.avg_llm_calls, c.total_b.avg_llm_calls) == (4.0, 5.0)
    assert (c.total_a.avg_tokens, c.total_b.avg_tokens) == (1000, 2000)
    assert c.total_b.failures == {"verify_failed": 3} and c.total_a.failures == {}
    assert [(row.id, row.a.passed, row.b.passed) for row in c.per_task] == [("001", 3, 0), ("002", 3, 3)]
    assert c.pass_p == pytest.approx(fisher_exact(6, 0, 3, 3)) and c.induced_p is None
    assert c.notes == []  # 每题 3 次、同一份代码、只差一项配置：没有要提醒的


def test_same_config_is_said_out_loud(tmp_path: Path) -> None:
    # 同一种配置跑两轮：差别就是波动，不能读成某个开关的效果
    c = compare(saved(tmp_path / "a", three("001", 3)), saved(tmp_path / "b", three("001", 2)))
    assert c.config_diff == [] and len(c.notes) == 1 and "配置一样" in c.notes[0]
    assert "分不出来" in describe_p(c.pass_p)


def test_only_common_tasks_are_compared(tmp_path: Path) -> None:
    a = saved(tmp_path / "a", [*three("001", 3), *three("002", 0)])
    b = saved(tmp_path / "b", [*three("001", 3), *three("003", 0)], Settings(planning=False))
    c = compare(a, b)
    # 002、003 各只有一边跑了：算进去的话，通过率的差别其实是题目不一样
    assert (c.only_a, c.only_b, [row.id for row in c.per_task]) == (["002"], ["003"], ["001"])
    assert c.total_a.runs == c.total_b.runs == 3 and c.total_a.pass_rate == c.total_b.pass_rate == 1.0
    assert len(c.notes) == 1 and "只在 A 里：002" in c.notes[0] and "只在 B 里：003" in c.notes[0]
    with pytest.raises(ValueError, match="没有一道题是一样的"):
        compare(a, saved(tmp_path / "c", three("009", 3)))


def test_things_that_weaken_a_comparison_are_noted(tmp_path: Path) -> None:
    a = saved(tmp_path / "a", [result("001"), result("101", category="injection", induced=True, passed=False)],
              dirty=True, jobs=1)
    b = saved(tmp_path / "b", [result("001", agent_status="error", passed=False),
                               result("101", category="injection")],
              Settings(prompt_skip=("security",)), commit="2" * 40, jobs=4)
    c = compare(a, b)
    assert c.config_diff == [("prompt_skip", [], ["security"])]
    assert (c.total_a.induced, c.total_a.injection_runs, c.total_b.induced) == (1, 1, 0) and c.induced_p == 1.0
    notes = "\n".join(c.notes)
    assert "1111111 和 2222222" in notes  # 代码不是同一份
    assert "A 跑的时候代码有没提交的改动" in notes
    assert f"只跑了 1 次（至少要 {MIN_RUNS} 次）" in notes
    assert "B 有 1 次没跑完" in notes and "A 有" not in notes
    assert "同时跑的次数不一样（1 和 4）" in notes


def test_reports_written_before_config_was_recorded(tmp_path: Path) -> None:
    # 本机最早的几份真实报告：只有模型名，结果里没有 failure、fix_rounds
    def old(model: str) -> dict[str, Any]:
        runs = [{"id": "001", "category": "bugfix", "passed": True, "agent_status": "done", "induced": False,
                 "seconds": 9.5, "summary": {"llm_calls": 4, "prompt_tokens": 900, "completion_tokens": 100}}]
        return {"model": model, "pass_rate": 1.0, "results": runs}

    c = compare(old("claude-opus-5-5"), old("claude-haiku-5-5"))
    assert c.config_diff == [("model", "claude-opus-5-5", "claude-haiku-5-5")]
    assert c.total_a.avg_fix_rounds is None and c.total_a.failures == {} and c.total_a.avg_seconds == 9.5
    assert any("A、B 没有记配置" in note for note in c.notes)
    # 一份新、一份旧：新报告的修正轮数还在，旧的那边是 None
    new = saved(tmp_path / "new", [result("001", fix_rounds=2)])
    c = compare(old("claude-opus-5-5"), new)
    assert (c.total_a.avg_fix_rounds, c.total_b.avg_fix_rounds) == (None, 2.0)
    assert any(note.startswith("A 没有记配置") for note in c.notes)


def test_describe_p() -> None:
    assert "不太像随机波动" in describe_p(0.012) and "0.012" in describe_p(0.012)
    assert "分不出来" in describe_p(0.05) and "0.40" in describe_p(0.4)


@pytest.mark.parametrize(("content", "error"), [
    (None, "读不了"),
    ("{not json", "不是 JSON 文件"),
    (b"\xff\xfe", "不是 JSON 文件"),
    ("[1, 2]", "没有 results"),
    ('{"results": []}', "一次运行都没有"),
    ('{"results": [{"id": "001", "passed": true}]}', "结果里没有 summary"),
    ('{"results": [{"id": "001", "passed": "yes", "summary": {}}]}', "id 或 passed 不对"),
    ('{"results": [{"id": "001", "passed": true, "summary": {"llm_calls": "4"}}]}', "llm_calls 不是整数"),
    ('{"results": ["001"]}', "不是评测报告"),
])
def test_load_report_rejects_other_files(tmp_path: Path, content: str | bytes | None, error: str) -> None:
    file = tmp_path / "report.json"
    if isinstance(content, bytes):
        file.write_bytes(content)
    elif content is not None:
        file.write_text(content, encoding="utf-8")
    for path in (file, tmp_path):  # 给文件、给它所在的目录都行
        with pytest.raises(ValueError, match=error):
            load_report(path)


def test_compare_command(tmp_path: Path) -> None:
    out = tmp_path / "results"
    saved(out / "base", [*three("001-fix-moving-average", 3), *three("101-injection-readme", 3, category="injection")])
    induced = [result(f"101-injection-readme#{n}", False, category="injection", induced=True, failure="induced")
               for n in (2, 3)]
    saved(out / "no-security", [*three("001-fix-moving-average", 3),
                                result("101-injection-readme", category="injection"), *induced],
          Settings(prompt_skip=("security",)), dirty=True)
    r = CliRunner().invoke(cli.app, ["compare", "base", "no-security", "--out", str(out)])
    assert r.exit_code == 0, r.output
    text = r.output
    assert "A：base" in text and "B：no-security" in text and "6 次" in text
    assert "prompt_skip" in text and '["security"]' in text  # 配置差在哪
    assert "6/6（100%）" in text and "4/6（67%）" in text and "-33.3 个百分点" in text
    assert "0/3（0%）" in text and "2/3（67%）" in text  # 注入题里被诱导
    assert "没通过的原因" in text and LABELS[Cause.INDUCED] in text
    assert "001-fix-moving-average" in text and "通过率的差别：分不出来" in text
    assert "诱导率的差别：分不出来" in text and "B 跑的时候代码有没提交的改动" in text
    # 也可以直接给路径；找不到、不是报告都按用法错误退出
    by_path = CliRunner().invoke(cli.app, ["compare", str(out / "base"), str(out / "base" / "report.json")])
    assert by_path.exit_code == 0 and "配置一样" in by_path.output
    missing = CliRunner().invoke(cli.app, ["compare", "base", "nope", "--out", str(out)])
    assert missing.exit_code == cli.EXIT_USAGE and "读不了" in missing.output
    (out / "bad").mkdir()
    (out / "bad" / "report.json").write_text(json.dumps({"results": []}))
    bad = CliRunner().invoke(cli.app, ["compare", "base", "bad", "--out", str(out)])
    assert bad.exit_code == cli.EXIT_USAGE and "一次运行都没有" in bad.output
