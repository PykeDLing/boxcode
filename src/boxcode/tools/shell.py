from pydantic import Field

from boxcode.tools.base import Risk, Target, Tool, ToolContext, ToolParams, ToolResult


class RunCommandParams(ToolParams):
    command: str = Field(min_length=1, description="Shell command, run with /bin/sh -c in the workspace root")
    timeout_s: int = Field(default=60, ge=1, le=600, description="Kill the command after this many seconds")


class RunCommand(Tool[RunCommandParams]):
    name = "run_command"
    description = (
        "Run a shell command in the workspace (the system prompt says what the sandbox allows). "
        "Background processes are stopped when the command returns, so a server started with `&` "
        "does not survive into the next call. Use it to run tests, linters and scripts."
    )
    risk = Risk.EXEC
    Params = RunCommandParams

    def target(self, ctx: ToolContext, params: RunCommandParams) -> Target:
        return Target(command=params.command)

    def run(self, ctx: ToolContext, params: RunCommandParams) -> ToolResult:
        timeout = min(params.timeout_s, ctx.settings.command_timeout_s)
        r = ctx.runner.run(params.command, ctx.workspace, timeout, cancel=ctx.cancel)
        if r.cancelled:
            head = "已被用户停止"
        elif r.timed_out:
            head = f"超过 {timeout} 秒，已结束"
        else:
            head = f"exit code: {r.exit_code}"
        return ToolResult(f"{head}\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}", ok=r.ok)
