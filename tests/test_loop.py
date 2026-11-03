"""主循环：用剧本模型走完“改代码 → 自检失败 → 再改 → 通过”。"""

from pathlib import Path

from boxcode.agent import Agent, Status
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.sandbox import NoSandboxRunner

CHECK = "grep -q 'value = 3' app.py"


def make_agent(llm: ScriptedProvider, workspace: Path, settings: Settings) -> Agent:
    return Agent(llm, workspace, NoSandboxRunner(), settings)


def test_edit_then_done(workspace: Path, settings: Settings) -> None:
    (workspace / "app.py").write_text("value = 1\n")
    llm = ScriptedProvider([
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 1", new_string="value = 3")]),
        LLMResponse("Changed value to 3."),
    ])
    result = make_agent(llm, workspace, settings).run("set value to 3", verify_command=CHECK)
    assert result.status is Status.DONE
    assert (workspace / "app.py").read_text() == "value = 3\n"
    assert result.trace.summary()["tool_calls"] == 1
    assert result.trace.path is not None and result.trace.path.exists()


def test_verify_failure_is_fed_back(workspace: Path, settings: Settings) -> None:
    (workspace / "app.py").write_text("value = 1\n")
    llm = ScriptedProvider([
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 1", new_string="value = 2")]),
        LLMResponse("Done."),  # 自检失败
        LLMResponse(None, [call("edit_file", path="app.py", old_string="value = 2", new_string="value = 3")]),
        LLMResponse("Fixed."),
    ])
    result = make_agent(llm, workspace, settings).run("set value to 3", verify_command=CHECK)
    assert result.status is Status.DONE and result.fix_rounds == 1
    feedback = llm.seen[2][-1]
    assert feedback["role"] == "user" and "failed" in feedback["content"]


def test_denied_and_invalid_calls_reach_model(workspace: Path, settings: Settings) -> None:
    llm = ScriptedProvider([
        LLMResponse(None, [
            call("write_file", path=".git/hooks/pre-commit", content="evil"),
            call("read_file", path="../outside"),
            call("no_such_tool"),
        ]),
        LLMResponse("ok"),
    ])
    result = make_agent(llm, workspace, settings).run("x")
    tool_msgs = [m for m in llm.seen[1] if m["role"] == "tool"]
    assert "拒绝" in tool_msgs[0]["content"]
    assert "不在工作区" in tool_msgs[1]["content"]
    assert "没有这个工具" in tool_msgs[2]["content"]
    assert result.trace.summary()["denied"] == 1
    assert not (workspace / ".git/hooks/pre-commit").exists()


def test_max_turns(workspace: Path, settings: Settings) -> None:
    from dataclasses import replace

    llm = ScriptedProvider([LLMResponse(None, [call("list_dir")]) for _ in range(5)])
    result = make_agent(llm, workspace, replace(settings, max_turns=3)).run("loop forever")
    assert result.status is Status.MAX_TURNS and result.turns == 3
