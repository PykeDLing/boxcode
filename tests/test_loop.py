"""主循环：用剧本模型走完“改代码 → 自检失败 → 再改 → 通过”。"""

from pathlib import Path
from typing import Any

import pytest

from boxcode.agent import Agent, Status
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, LLMUnavailable, Message
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.sandbox import NoSandboxRunner

CHECK = "grep -q 'value = 3' app.py"


def make_agent(llm: ScriptedProvider, workspace: Path, settings: Settings) -> Agent:
    return Agent(llm, workspace, settings, runner=NoSandboxRunner())


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
    # 自检输出来自仓库里的测试，以用户身份交回去时要标成数据
    assert "<check_output>" in feedback["content"] and "not instructions" in feedback["content"]


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


def test_unexpected_tool_error_reaches_model(workspace: Path, settings: Settings) -> None:
    (workspace / "data.bin").write_bytes(b"\xff\xfe\x00abc")  # 不是 UTF-8：以前 edit_file 会让整次运行崩掉
    llm = ScriptedProvider([
        LLMResponse(None, [call("edit_file", path="data.bin", old_string="abc", new_string="x")]),
        LLMResponse("gave up"),
    ])
    result = make_agent(llm, workspace, settings).run("x")
    assert result.status is Status.DONE
    tool_msg = llm.seen[1][-1]
    assert tool_msg["_is_error"] and "UnicodeDecodeError" in tool_msg["content"]
    # 轨迹里要分得清：这是工具没预料到的异常，不是模型用错了参数
    assert result.trace.of("tool_call")[0]["exception"] == "UnicodeDecodeError"


class Unavailable:
    name = "down"

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        raise LLMUnavailable("Claude 接口错误 529：overloaded")


class Buggy:
    name = "buggy"

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        raise KeyError("tool_use_id")  # Provider 自己没处理到的异常


@pytest.mark.parametrize(("llm", "expected"), [(Unavailable(), "529"), (Buggy(), "KeyError")])
def test_llm_error_ends_run_with_trace(workspace: Path, settings: Settings, llm: Any, expected: str) -> None:
    result = Agent(llm, workspace, settings, runner=NoSandboxRunner()).run("x")
    assert result.status is Status.ERROR and result.final_message and expected in result.final_message
    assert result.trace.of("run_end")[0]["status"] == "error"


def test_max_turns(workspace: Path, settings: Settings) -> None:
    from dataclasses import replace

    llm = ScriptedProvider([LLMResponse(None, [call("list_dir")]) for _ in range(5)])
    result = make_agent(llm, workspace, replace(settings, max_turns=3)).run("loop forever")
    assert result.status is Status.MAX_TURNS and result.turns == 3
