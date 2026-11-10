"""任务规划：模型把复杂任务拆成步骤，边做边更新。计划的每次变化都记进轨迹，界面上显示最新的一份。

只记录、不碰工作区，所以风险级别是 read，只读模式下也能用。
"""

from typing import Literal

from pydantic import Field, model_validator

from boxcode.tools.base import Risk, Tool, ToolContext, ToolParams, ToolResult

PLAN_TOOL = "update_plan"
PLAN_EVENT = "plan_update"


class PlanStep(ToolParams):
    step: str = Field(min_length=1, max_length=300, description="What this step does, in one short sentence")
    status: Literal["pending", "in_progress", "completed"]


class UpdatePlanParams(ToolParams):
    steps: list[PlanStep] = Field(min_length=1, max_length=30, description="The whole plan, in order")

    @model_validator(mode="after")
    def _one_in_progress(self) -> "UpdatePlanParams":
        if sum(s.status == "in_progress" for s in self.steps) > 1:
            raise ValueError("at most one step can be in_progress")
        return self


class UpdatePlan(Tool[UpdatePlanParams]):
    name = PLAN_TOOL
    description = (
        "Write or replace the plan for this task. Send the whole list every time, with at most one step in_progress. "
        "Use it for tasks with several distinct steps; skip it for a simple fix."
    )
    risk = Risk.READ
    Params = UpdatePlanParams

    def run(self, ctx: ToolContext, params: UpdatePlanParams) -> ToolResult:
        steps = [s.model_dump() for s in params.steps]
        completed = sum(s.status == "completed" for s in params.steps)
        ctx.record(PLAN_EVENT, steps=steps, completed=completed, total=len(steps))
        return ToolResult(f"Plan updated: {completed}/{len(steps)} steps completed.")
