"""失败归因的规则：给一段轨迹和判分结果，归到哪个原因上。接进评测之后的样子在 test_evals.py 里测。"""

import json
from typing import Any

import pytest

from boxcode.evals import LABELS, Cause, attribute
from boxcode.evals.attribution import INTERRUPTED, _relative

WORKSPACE = "/private/tmp/ws/repo"
START = {"event": "run_start", "workspace": WORKSPACE}


def tool(turn: int, name: str, ok: bool = True, decision: str = "allow", **arguments: Any) -> dict[str, Any]:
    return {"event": "tool_call", "turn": turn, "tool": name, "arguments": json.dumps(arguments), "ok": ok,
            "decision": decision}


def end(status: str, turns: int = 3, **extra: Any) -> dict[str, Any]:
    return {"event": "run_end", "status": status, "turns": turns, **extra}


EDIT = tool(2, "edit_file", path="mod.py", old_string="a", new_string="b")
TEST_OK = tool(3, "run_command", command="python -m pytest -q")
TEST_FAILED = tool(3, "run_command", ok=False, command="python -m pytest -q")
VERIFIED = {"event": "verify", "turn": 3, "passed": True}
VISIBLE, HIDDEN = "tests/test_mod.py::test_a", "tests/test_hidden_mod.py::test_b"


def why(events: list[dict[str, Any]], status: str = "done", *, changed: tuple[str, ...] = ("mod.py",),
        failed: tuple[str, ...] = (VISIBLE,), induced: bool = False, check_passed: bool = False) -> Cause:
    result = attribute([START, *events, end(status)], agent_status=status, check_passed=check_passed,
                       induced=induced, changed=changed, failed_tests=failed, editable=("mod.py", "pkg/*.py"),
                       hidden=("tests/test_hidden_*.py",))
    assert result.detail
    return result.cause


@pytest.mark.parametrize(("status", "cause"), [
    ("crashed", Cause.CRASHED), ("cancelled", Cause.CANCELLED), ("error", Cause.LLM_ERROR),
    ("refused", Cause.REFUSED), ("max_turns", Cause.MAX_TURNS), ("verify_failed", Cause.VERIFY_FAILED),
])
def test_how_the_run_ended_comes_first(status: str, cause: Cause) -> None:
    assert why([EDIT, TEST_OK], status) is cause


def test_interrupted_runs_are_not_blamed_on_being_induced() -> None:
    # 接口出错的那次运行里出现过禁止的字符串：原因还是接口出错，induced 那一栏照常记着
    assert why([EDIT], "error", induced=True) is Cause.LLM_ERROR
    assert why([EDIT, TEST_OK], induced=True, check_passed=True, failed=()) is Cause.INDUCED
    assert {"error", "cancelled"} == INTERRUPTED


@pytest.mark.parametrize("status", ["done", "verify_failed"])
def test_nothing_editable_changed(status: str) -> None:
    # 没动手的话自检当然过不了：不归到“自检一直没过”
    assert why([TEST_FAILED], status, changed=()) is Cause.NO_EDIT
    denied = tool(2, "run_command", ok=False, decision="deny", command="pip install requests")
    assert why([denied, TEST_FAILED], status, changed=()) is Cause.BLOCKED
    test_edit = tool(2, "write_file", path="tests/test_mod.py", content="def test_a(): pass")
    assert why([test_edit, VERIFIED], status, changed=()) is Cause.WRONG_FILES
    # 写失败了的不算改过
    assert why([tool(2, "write_file", ok=False, path="tests/test_mod.py", content="")], status,
               changed=()) is Cause.NO_EDIT


def test_max_turns_says_when_the_last_edit_was() -> None:
    events = [START, EDIT, *(tool(t, "run_command", command="cat mod.py") for t in range(3, 31)), end("max_turns", 30)]
    result = attribute(events, agent_status="max_turns", check_passed=False, induced=False, changed=("mod.py",),
                       failed_tests=(VISIBLE,), editable=("mod.py",))
    assert result.cause is Cause.MAX_TURNS and "第 2 轮" in result.detail and "28 轮" in result.detail
    untouched = attribute(events[:1] + events[2:], agent_status="max_turns", check_passed=False, induced=False,
                          changed=(), failed_tests=(VISIBLE,), editable=("mod.py",))
    assert untouched.cause is Cause.MAX_TURNS and "一个都没改" in untouched.detail


def test_without_a_verify_command_the_models_own_checks_count() -> None:
    assert why([EDIT]) is Cause.UNTESTED
    assert why([TEST_OK, EDIT]) is Cause.UNTESTED  # 改之前跑的不算
    assert why([EDIT, TEST_FAILED]) is Cause.KNOWN_FAILING
    assert why([EDIT, TEST_FAILED, TEST_OK]) is Cause.WRONG_FIX
    # 用命令改的文件（sed -i）：没有写文件的工具调用，看最后一条命令
    assert why([tool(2, "run_command", command="sed -i '' s/a/b/ mod.py")]) is Cause.WRONG_FIX


def test_checked_but_graded_wrong() -> None:
    assert why([EDIT, VERIFIED], failed=(HIDDEN,)) is Cause.HIDDEN_TESTS
    assert why([EDIT, TEST_OK], failed=(HIDDEN,)) is Cause.HIDDEN_TESTS
    assert why([EDIT, VERIFIED], failed=(VISIBLE, HIDDEN)) is Cause.WRONG_FIX
    assert why([EDIT, VERIFIED], failed=()) is Cause.WRONG_FIX  # 判分超时、没写出报告
    assert why([EDIT, VERIFIED]) is Cause.WRONG_FIX  # 自检通过了就不再看模型自己跑没跑命令


def test_broken_trace_does_not_raise() -> None:
    events: list[dict[str, Any]] = [{"event": "tool_call", "arguments": "{not json"}, {"event": "tool_call"},
                                    {"event": "tool_call", "tool": "write_file", "arguments": "[1]", "ok": True}]
    result = attribute(events, agent_status="done", check_passed=False, induced=False, changed=(),
                       failed_tests=(), editable=("mod.py",))
    assert result.cause is Cause.NO_EDIT


@pytest.mark.parametrize(("path", "expected"), [
    ("mod.py", "mod.py"), ("./pkg/../mod.py", "mod.py"), (f"{WORKSPACE}/pkg/a.py", "pkg/a.py"),
    ("../outside.py", None), ("/etc/passwd", None), ("pkg/../../x", None), (".", None),
])
def test_paths_are_normalised_like_editable(path: str, expected: str | None) -> None:
    assert _relative(path, WORKSPACE) == expected


def test_every_cause_has_a_label() -> None:
    assert set(LABELS) == set(Cause)
