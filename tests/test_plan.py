"""任务规划：update_plan 只记录，每次变化进轨迹，开关能关掉工具和提示。"""

from pathlib import Path
from typing import Any

from boxcode.agent import Agent
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, SystemMessage, ToolResultMessage
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.policy import ApprovalMode, ExecutionPolicy
from boxcode.sandbox import NoSandboxRunner


def steps(*statuses: str) -> list[dict[str, Any]]:
    return [{"step": f"step {i}", "status": s} for i, s in enumerate(statuses)]


def run_plan(
    workspace: Path, settings: Settings, plan: list[dict[str, Any]], **kw: Any,
) -> tuple[Any, ScriptedProvider]:
    llm =ScriptedProvider([LLMResponse(None, [call("update_plan", steps=plan)]), LLMResponse("ok")])
    return Agent(llm, workspace, settings, runner=NoSandboxRunner(), **kw).run("x"), llm


def test_plan_is_recorded_with_turn(workspace: Path, settings: Settings) -> None:
    result, llm = run_plan(workspace, settings, steps("completed", "in_progress", "pending"))
    event = result.trace.of("plan_update")[0]
    assert event["turn"] == 1 and event["completed"] == 1 and event["total"] == 3
    assert event["steps"][1] == {"step": "step 1", "status": "in_progress"}
    assert result.trace.summary()["plan_updates"] == 1
    reply = llm.seen[1][-1]
    assert isinstance(reply, ToolResultMessage) and reply.content == "Plan updated: 1/3 steps completed."


def test_every_change_is_recorded(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse(None, [call("update_plan", steps=steps("in_progress", "pending"))]),
                            LLMResponse(None, [call("update_plan", steps=steps("completed", "in_progress"))]),
                            LLMResponse("ok")])
    result = Agent(llm, workspace, settings, runner=NoSandboxRunner()).run("x")
    assert [e["completed"] for e in result.trace.of("plan_update")] == [0, 1]


def test_two_steps_in_progress_rejected(workspace: Path, settings: Settings) -> None:
    result, llm = run_plan(workspace, settings, steps("in_progress", "in_progress"))
    assert not result.trace.of("plan_update")
    reply = llm.seen[1][-1]
    assert isinstance(reply, ToolResultMessage) and reply.is_error and "at most one step" in reply.content


def test_empty_plan_rejected(workspace: Path, settings: Settings) -> None:
    result, llm = run_plan(workspace, settings, [])
    reply = llm.seen[1][-1]
    assert isinstance(reply, ToolResultMessage) and reply.is_error and not result.trace.of("plan_update")


def test_unknown_field_rejected(workspace: Path, settings: Settings) -> None:
    result, _ = run_plan(workspace, settings, [{"step": "a", "status": "pending", "owner": "me"}])
    assert not result.trace.of("plan_update")


def test_allowed_in_read_only_mode(workspace: Path, settings: Settings) -> None:
    result, _ = run_plan(workspace, settings, steps("pending"), execution=ExecutionPolicy(ApprovalMode.READ_ONLY))
    assert result.trace.of("tool_call")[0]["decision"] == "allow" and result.trace.of("plan_update")


def test_plan_does_not_touch_workspace(workspace: Path, settings: Settings) -> None:
    run_plan(workspace, settings, steps("pending"))
    assert list(workspace.iterdir()) == []


def test_prompt_mentions_planning_when_tool_exists(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse("ok")])
    Agent(llm, workspace, settings, runner=NoSandboxRunner()).run("x")
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage) and "update_plan" in system.content
    assert "update_plan" in {t.name for t in llm.tools}


def test_planning_can_be_turned_off(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([LLMResponse("ok")])
    custom = settings.model_copy(update={"planning": False})
    result = Agent(llm, workspace, custom, runner=NoSandboxRunner()).run("x")
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage) and "update_plan" not in system.content
    assert "update_plan" not in {t.name for t in llm.tools}
    assert result.trace.of("run_start")[0]["planning"] is False
