from pydantic import BaseModel, Field

from boxcode.tools.base import Risk, Target, Tool, ToolContext, ToolResult, truncate


class RunCommand(Tool):
    name = "run_command"
    description = (
        "Run a shell command in the workspace (the system prompt says what the sandbox allows). "
        "Background processes are stopped when the command returns, so a server started with `&` "
        "does not survive into the next call. Use it to run tests, linters and scripts."
    )
    risk = Risk.EXEC

    class Params(BaseModel):
        command: str = Field(min_length=1)
        timeout_s: int = Field(default=60, ge=1, le=600)

    def target(self, ctx: ToolContext, params: BaseModel) -> Target:
        assert isinstance(params, RunCommand.Params)
        return Target(command=params.command)

    def run(self, ctx: ToolContext, params: Params) -> ToolResult:
        timeout = min(params.timeout_s, ctx.settings.command_timeout_s)
        r = ctx.runner.run(params.command, ctx.workspace, timeout)
        head = "超时，已结束" if r.timed_out else f"exit code: {r.exit_code}"
        body = f"{head}\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"
        return ToolResult(truncate(body, ctx.settings.max_tool_output), ok=r.exit_code == 0 and not r.timed_out)
