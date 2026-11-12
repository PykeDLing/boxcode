"""对比两份评测报告（技术方案 5.3 的对比实验）。

对比实验是换一项配置、把同一批题再跑一遍，然后比两份 report.json。这里回答三个问题：

- 两轮差在哪：报告里记着整份配置和代码的提交号，逐项比
- 指标差多少：只比两边都跑了的题，不然题目难度不一样，比不出东西
- 通过率的差别是不是可能只是随机波动：Fisher 精确检验。每题只跑一两次时差别再大也分不出来，这里直接说出来，
  免得把一次运行的偶然当成结论

只读报告，不调模型，也不读轨迹；旧报告缺的字段（配置、修正轮数、没通过的原因）按没记处理。
"""

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from math import comb
from pathlib import Path
from typing import Any

from boxcode.evals.attribution import INTERRUPTED

# 每题至少跑这么多次才值得比（5.3）
MIN_RUNS = 3
# p 低于它才说“不太像随机波动”
NOISE_P = 0.05


@dataclass(frozen=True)
class Side:
    """一份报告里的一组运行（全部，或者某一道题的几次）汇总出来的数。"""

    runs: int
    passed: int
    injection_runs: int
    induced: int  # 注入题里被诱导的次数
    interrupted: int  # 接口出错或被停止、没跑完的次数
    avg_llm_calls: float
    avg_tokens: int
    avg_seconds: float
    avg_fix_rounds: float | None  # 报告里没记（加这一项之前跑的）是 None
    failures: dict[str, int]  # 没通过的原因 → 次数

    @property
    def pass_rate(self) -> float:
        return self.passed / self.runs


@dataclass(frozen=True)
class TaskRow:
    id: str
    category: str
    a: Side
    b: Side


@dataclass(frozen=True)
class Comparison:
    # 不一样的配置项：（名字，A 的值，B 的值）；哪一边没记这一项，值是 None
    config_diff: list[tuple[str, Any, Any]]
    total_a: Side
    total_b: Side
    # 假设两边其实一样，随机波动出现这么大（或更大）差别的概率
    pass_p: float
    induced_p: float | None  # 两边都有注入题才有
    per_task: list[TaskRow]
    # 只有一边跑了的题，不参加比较
    only_a: list[str]
    only_b: list[str]
    # 读这份对比时要留意的事，直接给用户看
    notes: list[str]


def fisher_exact(a_yes: int, a_no: int, b_yes: int, b_no: int) -> float:
    """2×2 表的 Fisher 精确检验（双侧）。

    把两边的运行混在一起、再随机分成同样大小的两组，“是”的分布和观察到的一样极端（或更极端）的概率。
    把每一次运行当成独立的：同一道题的几次其实更像，所以算出来的 p 偏小，只能当粗略的参考。
    """
    yes, no, a = a_yes + b_yes, a_no + b_no, a_yes + a_no
    ways = comb(yes + no, a)

    def prob(k: int) -> float:
        return comb(yes, k) * comb(no, a - k) / ways

    observed = prob(a_yes)
    # 比观察到的更不可能的分法都算上；乘一点余量：一样极端的分法不能因为浮点误差漏掉
    return min(1.0, sum(p for k in range(max(0, a - no), min(yes, a) + 1) if (p := prob(k)) <= observed * (1 + 1e-9)))


def load_report(path: Path) -> dict[str, Any]:
    """读一份报告：path 是 report.json，或者它所在的目录。读不了、不是评测报告时抛 ValueError（消息给用户看）。"""
    file = path / "report.json" if path.is_dir() else path
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"读不了 {file}：{e.strerror or e}") from None
    except ValueError:  # 不是 JSON，或者不是 UTF-8
        raise ValueError(f"{file} 不是 JSON 文件") from None
    try:
        _check(data)
    except KeyError as e:
        raise ValueError(f"{file} 不是评测报告：结果里没有 {e.args[0]}") from None
    except (TypeError, ValueError) as e:
        raise ValueError(f"{file} 不是评测报告：{e}") from None
    return dict(data)


def _check(report: Any) -> None:
    """后面要用到的字段都在、类型都对。旧报告没有的字段（配置、原因、修正轮数）不查。"""
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        raise ValueError("没有 results")
    if not report["results"]:
        raise ValueError("一次运行都没有")
    for r in report["results"]:
        if not isinstance(r["id"], str) or not isinstance(r["passed"], bool):
            raise ValueError("结果里的 id 或 passed 不对")
        for key in ("llm_calls", "prompt_tokens", "completion_tokens"):
            if not isinstance(r["summary"][key], int):
                raise ValueError(f"结果里的 {key} 不是整数")


def _by_task(report: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """同一道题的几次（`题目#2`、`题目#3`）放在一起，顺序照报告里的。"""
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in report["results"]:
        groups.setdefault(r["id"].partition("#")[0], []).append(r)
    return groups


def _side(runs: list[dict[str, Any]]) -> Side:
    n = len(runs)
    injection = [r for r in runs if r.get("category") == "injection"]
    fix_rounds = [r.get("fix_rounds") for r in runs]
    known = [f for f in fix_rounds if isinstance(f, int)]
    return Side(
        runs=n,
        passed=sum(r["passed"] for r in runs),
        injection_runs=len(injection),
        induced=sum(bool(r.get("induced")) for r in injection),
        interrupted=sum(r.get("agent_status") in INTERRUPTED for r in runs),
        avg_llm_calls=round(sum(r["summary"]["llm_calls"] for r in runs) / n, 2),
        avg_tokens=round(sum(r["summary"]["prompt_tokens"] + r["summary"]["completion_tokens"] for r in runs) / n),
        avg_seconds=round(sum(float(r.get("seconds") or 0) for r in runs) / n, 1),
        avg_fix_rounds=round(sum(known) / n, 2) if len(known) == n else None,
        failures=dict(Counter(str(r["failure"]) for r in runs if r.get("failure")).most_common()),
    )


def _config_diff(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[tuple[str, Any, Any]]:
    config_a, config_b = a.get("config"), b.get("config")
    if not isinstance(config_a, dict) or not isinstance(config_b, dict):
        # 旧报告只记了模型名
        return [("model", a.get("model"), b.get("model"))] if a.get("model") != b.get("model") else []
    return [(key, config_a.get(key), config_b.get(key)) for key in dict.fromkeys([*config_a, *config_b])
            if config_a.get(key) != config_b.get(key)]


def _notes(a: Mapping[str, Any], b: Mapping[str, Any], result: Comparison) -> list[str]:
    notes = []
    if result.only_a or result.only_b:
        extra = "；".join(f"只在 {name} 里：{'、'.join(ids)}"
                         for name, ids in (("A", result.only_a), ("B", result.only_b)) if ids)
        notes.append(f"只比两边都有的 {len(result.per_task)} 道题。{extra}")
    sides = (("A", a, result.total_a), ("B", b, result.total_b))
    no_config = [name for name, report, _ in sides if not isinstance(report.get("config"), dict)]
    if no_config:
        notes.append(f"{'、'.join(no_config)} 没有记配置（加这项记录之前跑的）：配置差在哪看不全")
    elif not result.config_diff:
        notes.append("两份报告的配置一样：下面的差别就是同一种配置两轮之间的波动")
    codes: list[dict[str, Any]] = [code if isinstance(code := report.get("boxcode"), dict) else {}
                                   for _, report, _ in sides]
    commit_a, commit_b = (code.get("commit") for code in codes)
    if isinstance(commit_a, str) and isinstance(commit_b, str) and commit_a != commit_b:
        notes.append(f"代码不是同一份（{commit_a[:7]} 和 {commit_b[:7]}）：差别也可能来自代码的改动")
    dirty = [name for (name, _, _), code in zip(sides, codes, strict=True) if code.get("dirty")]
    if dirty:
        notes.append(f"{'、'.join(dirty)} 跑的时候代码有没提交的改动：光凭提交号对不上当时的代码")
    fewest = min(min(row.a.runs, row.b.runs) for row in result.per_task)
    if fewest < MIN_RUNS:
        notes.append(f"有的题每边只跑了 {fewest} 次（至少要 {MIN_RUNS} 次）：模型的输出有随机性，"
                     "单看某一道题的差别说明不了什么")
    for name, _, side in sides:
        if side.interrupted:
            notes.append(f"{name} 有 {side.interrupted} 次没跑完（模型接口出错或被停止），通过率里照常算了；"
                         "要比的话先把这几次重跑")
    jobs_a, jobs_b = a.get("jobs", 1), b.get("jobs", 1)
    if jobs_a != jobs_b:
        notes.append(f"同时跑的次数不一样（{jobs_a} 和 {jobs_b}）：耗时不能直接比")
    return notes


def compare(a: Mapping[str, Any], b: Mapping[str, Any]) -> Comparison:
    """a 是基准，b 是换了配置的那一轮（都是 load_report 读出来的）。没有两边都跑了的题时抛 ValueError。"""
    tasks_a, tasks_b = _by_task(a), _by_task(b)
    common = [task_id for task_id in tasks_a if task_id in tasks_b]
    if not common:
        raise ValueError("两份报告没有一道题是一样的，没法比")
    per_task = [TaskRow(task_id, str(tasks_a[task_id][0].get("category", "")),
                        _side(tasks_a[task_id]), _side(tasks_b[task_id])) for task_id in common]
    total_a = _side([r for task_id in common for r in tasks_a[task_id]])
    total_b = _side([r for task_id in common for r in tasks_b[task_id]])
    induced_p = None
    if total_a.injection_runs and total_b.injection_runs:
        induced_p = fisher_exact(total_a.induced, total_a.injection_runs - total_a.induced,
                                 total_b.induced, total_b.injection_runs - total_b.induced)
    result = Comparison(
        config_diff=_config_diff(a, b), total_a=total_a, total_b=total_b,
        pass_p=fisher_exact(total_a.passed, total_a.runs - total_a.passed,
                            total_b.passed, total_b.runs - total_b.passed),
        induced_p=induced_p, per_task=per_task,
        only_a=[task_id for task_id in tasks_a if task_id not in tasks_b],
        only_b=[task_id for task_id in tasks_b if task_id not in tasks_a],
        notes=[],
    )
    return replace(result, notes=_notes(a, b, result))


def describe_p(p: float) -> str:
    """把 p 说成人话。"""
    if p < NOISE_P:
        return f"不太像随机波动（两边其实一样的话，碰巧差这么多的概率 p = {p:.3f}）"
    return f"分不出来，可能只是随机波动（两边其实一样的话，碰巧差这么多的概率 p = {p:.2f}）"
