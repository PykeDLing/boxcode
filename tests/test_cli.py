"""命令行：前两个问题是在终端里端到端跑的时候发现的。"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest
from rich.status import Status
from typer.testing import CliRunner

from boxcode import __version__, cli
from boxcode.config import Settings
from boxcode.llm.base import LLMResponse, LLMUnavailable, Message, ToolSpec
from boxcode.llm.scripted import ScriptedProvider
from boxcode.policy import Action, Decision
from boxcode.tools import RunCommand
from tests.conftest import macos_only


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

    monkeypatch.setattr("boxcode.cli.Confirm.ask", no_input)
    status = FakeStatus()
    params = RunCommand.Params(command="curl x")
    assert cli.ask_user(cast(Status, status), RunCommand(), params, Decision(Action.ASK, "高风险命令")) is False
    assert status.calls == ["stop", "start"]


class Unavailable:
    name = "down"

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec], *, cancel: object = None) -> LLMResponse:
        raise LLMUnavailable("Claude 接口错误 529：overloaded")


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("BOXCODE_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_run_exits_nonzero_when_not_done(monkeypatch: pytest.MonkeyPatch, workspace: Path, home: Path) -> None:
    def make(_: Settings) -> Unavailable:
        return Unavailable()

    monkeypatch.setattr(cli, "make_provider", make)
    r = CliRunner().invoke(cli.app, ["run", "x", "-w", str(workspace), "--dangerously-no-sandbox"])
    assert r.exit_code == cli.EXIT_NOT_DONE and "error" in r.output and "529" in r.output
    assert list((home / "runs").glob("*.jsonl"))  # 轨迹写到了 BOXCODE_HOME


def test_bad_config_exits_with_usage_error(monkeypatch: pytest.MonkeyPatch, workspace: Path) -> None:
    monkeypatch.setenv("BOXCODE_MAX_TURNS", "many")
    r = CliRunner().invoke(cli.app, ["run", "x", "-w", str(workspace)])
    assert r.exit_code == cli.EXIT_USAGE and "BOXCODE_MAX_TURNS" in r.output


def test_unsafe_workspace_refused_before_running(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setattr(cli, "make_provider", lambda _: Unavailable())
    r = CliRunner().invoke(cli.app, ["run", "x", "-w", str(Path.home()), "--dangerously-no-sandbox"])
    assert r.exit_code == cli.EXIT_USAGE and "主目录" in r.output
    assert not (home / "runs").exists()  # 一次都没有运行


@macos_only
def test_eval_report_records_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, home: Path) -> None:
    monkeypatch.setenv("BOXCODE_EFFORT", "low")
    monkeypatch.setenv("BOXCODE_PLANNING", "false")
    monkeypatch.setattr(cli, "make_provider", lambda _: ScriptedProvider([LLMResponse("done")]))
    tasks = Path(__file__).parent.parent / "evals" / "tasks"
    r = CliRunner().invoke(cli.app, ["eval", "--tasks", str(tasks), "--only", "001-fix-moving-average",
                                     "--out", str(tmp_path / "results")])
    assert r.exit_code == 0, r.output
    (report_path,) = (tmp_path / "results").glob("*/report.json")
    rep = json.loads(report_path.read_text())
    assert (rep["config"]["effort"], rep["config"]["planning"]) == ("low", False)
    assert set(rep["boxcode"]) == {"version", "commit", "dirty"} and rep["runs"] == 1


def test_version() -> None:
    r = CliRunner().invoke(cli.app, ["--version"])
    assert r.exit_code == 0 and __version__ in r.output
