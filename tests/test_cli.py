"""命令行：这两个问题是在终端里端到端跑的时候发现的。"""

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from boxcode import cli
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, LLMUnavailable, Message
from boxcode.policy import Action, Decision
from boxcode.tools import RunCommand


class FakeStatus:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def stop(self) -> None:
        self.calls.append("stop")

    def start(self) -> None:
        self.calls.append("start")


def test_ask_user_pauses_spinner_and_eof_means_no(monkeypatch: pytest.MonkeyPatch) -> None:
    # 转圈动画不停下来，会把“放行这一次？”那一行盖住
    def no_input(*_: Any, **__: Any) -> bool:
        raise EOFError

    monkeypatch.setattr(cli.Confirm, "ask", no_input)
    status = FakeStatus()
    params = RunCommand.Params(command="curl x")
    assert cli.ask_user(status, RunCommand(), params, Decision(Action.ASK, "高风险命令")) is False
    assert status.calls == ["stop", "start"]


class Unavailable:
    name = "down"

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        raise LLMUnavailable("Claude 接口错误 529：overloaded")


def test_run_exits_nonzero_when_not_done(monkeypatch: pytest.MonkeyPatch, workspace: Path, tmp_path: Path) -> None:
    def make(_: Settings) -> Unavailable:
        return Unavailable()

    monkeypatch.setattr(cli, "make_provider", make)
    monkeypatch.setenv("BOXCODE_HOME", str(tmp_path / "home"))
    r = CliRunner().invoke(cli.app, ["run", "x", "-w", str(workspace), "--dangerously-no-sandbox"])
    assert r.exit_code == 1 and "error" in r.output and "529" in r.output
