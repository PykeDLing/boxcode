"""上下文压缩：旧的工具结果换成说明，历史本身不改，前缀在两次清理之间不变。"""

from pathlib import Path

from boxcode.agent import Agent
from boxcode.agent.compaction import (
    ContextCompactor,
    estimate_tokens,
    message_tokens,
    placeholder,
)
from boxcode.config import Settings
from boxcode.llm.base import (
    AssistantMessage,
    LLMResponse,
    Message,
    Native,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from boxcode.llm.claude import convert_messages
from boxcode.llm.scripted import ScriptedProvider, call
from boxcode.sandbox import NoSandboxRunner

BIG = "x" * 7000  # 约 2000 token


def conversation(turns: int, output: str = BIG, same_id: bool = False) -> list[Message]:
    messages: list[Message] = [SystemMessage("system"), UserMessage("task")]
    for i in range(turns):
        call_id = "call_0" if same_id else f"call_{i}"
        messages.append(AssistantMessage(None, (ToolCall(call_id, "read_file", f'{{"path": "f{i}.py"}}'),)))
        messages.append(ToolResultMessage(call_id, f"{i}:{output}"))
    return messages


def contents(messages: list[Message]) -> list[str]:
    return [m.content for m in messages if isinstance(m, ToolResultMessage)]


def test_estimate_counts_cjk_higher_than_ascii() -> None:
    assert estimate_tokens("a" * 35) == 10
    assert estimate_tokens("中" * 15) == 10
    assert estimate_tokens("") == 0


def test_below_threshold_nothing_changes() -> None:
    messages = conversation(3)
    compactor = ContextCompactor(100_000)
    assert compactor.compact(messages) is None
    assert compactor.view(messages) == messages


def test_zero_threshold_means_off() -> None:
    messages = conversation(30)
    compactor = ContextCompactor(0)
    assert compactor.compact(messages) is None
    assert compactor.view(messages) == messages


def test_over_threshold_clears_oldest_and_keeps_history() -> None:
    messages = conversation(8)
    original = list(messages)
    compactor = ContextCompactor(10_000)
    done = compactor.compact(messages)
    assert done is not None and done.after_tokens <= compactor.target < done.before_tokens
    assert messages == original  # 历史只追加、不修改
    results = contents(compactor.view(messages))
    assert "output cleared" in results[0]
    # 最近两轮的结果不动：模型多半正要用
    assert results[-1] == contents(original)[-1] and results[-2] == contents(original)[-2]


def test_only_clears_down_to_target() -> None:
    # 清到阈值的一半就停，不是把能清的全清掉
    compactor = ContextCompactor(14_000)
    messages = conversation(10)
    assert compactor.compact(messages) is not None
    results = contents(compactor.view(messages))
    cleared = [i for i, r in enumerate(results) if "output cleared" in r]
    assert cleared == list(range(len(cleared))) and 0 < len(cleared) < len(results) - 2


def test_prefix_stays_identical_between_compactions() -> None:
    # 提示缓存按前缀匹配：清理之后到下一次超过阈值之前，发出去的前缀必须一个字节都不变
    messages = conversation(8)
    compactor = ContextCompactor(10_000)
    assert compactor.compact(messages) is not None
    first = compactor.view(messages)
    messages.append(AssistantMessage(None, (ToolCall("new", "read_file", "{}"),)))
    messages.append(ToolResultMessage("new", "short"))
    assert compactor.compact(messages) is None
    assert compactor.view(messages)[: len(first)] == first


def test_batches_stay_apart_when_recent_results_fill_the_budget() -> None:
    # 实测：最近两轮的结果本身就接近阈值，清理之后马上又超过，每一轮都清理、缓存轮轮失效
    messages = conversation(3)
    compactor = ContextCompactor(5000)
    compactions = 0
    for i in range(3, 23):
        messages.append(AssistantMessage(None, (ToolCall(f"c{i}", "read_file", "{}"),)))
        messages.append(ToolResultMessage(f"c{i}", BIG))
        compactions += compactor.compact(messages) is not None
    assert 0 < compactions <= 12


def test_cleared_results_stay_cleared() -> None:
    messages = conversation(8)
    compactor = ContextCompactor(10_000)
    compactor.compact(messages)
    before = sum("output cleared" in r for r in contents(compactor.view(messages)))
    messages.extend(conversation(10)[2:])
    assert compactor.compact(messages) is not None
    results = contents(compactor.view(messages))
    assert all("output cleared" in r for r in results[:before])
    assert sum("output cleared" in r for r in results) > before


def test_real_usage_triggers_even_when_estimate_is_small() -> None:
    # 接口报的真实用量（含系统提示、工具定义、思考块）比按字符估算准
    messages = conversation(6)
    compactor = ContextCompactor(50_000)
    assert compactor.compact(messages) is None
    compactor.observe(60_000, len(messages))
    assert compactor.compact(messages) is not None


def test_zero_usage_falls_back_to_estimate() -> None:
    messages = conversation(8)
    compactor = ContextCompactor(10_000)
    compactor.observe(0, len(messages))  # Ollama 这类接口可能不报用量
    assert compactor.compact(messages) is not None


def test_context_size_after_compaction_uses_view() -> None:
    messages = conversation(8)
    compactor = ContextCompactor(10_000)
    done = compactor.compact(messages)
    assert done is not None
    assert compactor.context_tokens(messages) == sum(message_tokens(m) for m in compactor.view(messages))


def test_repeated_tool_call_ids_clear_only_that_result() -> None:
    # 有的本地模型每轮都发一样的 id：按 id 替换会把最新的结果也换掉
    messages = conversation(8, same_id=True)
    compactor = ContextCompactor(10_000)
    assert compactor.compact(messages) is not None
    results = contents(compactor.view(messages))
    assert "output cleared" in results[0] and results[-1].startswith("7:")


def test_repeated_ids_in_one_turn_pair_by_position() -> None:
    # 同一轮两个调用都叫 call_0：按 id 对应会把 run_command 的结果当成 read_file，丢掉退出码
    output = "exit code: 1\n" + "noise\n" * 2000
    messages: list[Message] = [
        SystemMessage("s"), UserMessage("t"),
        AssistantMessage(None, (ToolCall("call_0", "run_command", "{}"), ToolCall("call_0", "read_file", "{}"))),
        ToolResultMessage("call_0", output), ToolResultMessage("call_0", BIG),
        *conversation(8)[2:],
    ]
    compactor = ContextCompactor(10_000)
    assert compactor.compact(messages) is not None
    results = contents(compactor.view(messages))
    assert results[0].startswith("[run_command output") and "exit code: 1" in results[0]
    assert results[1].startswith("[read_file output")


def test_placeholder_never_grows_a_result() -> None:
    messages = conversation(10, output="short line\n" * 57)
    messages[3] = ToolResultMessage("call_0", "exit code: 1\n" + "L" * 620)
    messages[2] = AssistantMessage(None, (ToolCall("call_0", "run_command", "{}"),))
    compactor = ContextCompactor(1000)
    compactor.compact(messages)
    view = compactor.view(messages)
    first = view[3]
    assert isinstance(first, ToolResultMessage) and len(first.content) <= 633


def test_short_results_are_left_alone() -> None:
    # 清理一次要重建缓存，几十个字符的结果不值得
    messages = conversation(40, output="ok")
    messages[1] = UserMessage("x" * 70_000)
    compactor = ContextCompactor(10_000)
    assert compactor.compact(messages) is None
    assert compactor.view(messages) == messages


def test_small_saving_is_not_worth_breaking_the_cache() -> None:
    messages = conversation(4, output="y" * 700)
    messages[1] = UserMessage("x" * 40_000)
    compactor = ContextCompactor(10_000)
    assert compactor.compact(messages) is None


def test_nothing_clearable_with_only_recent_turns() -> None:
    messages = conversation(2, output="z" * 80_000)
    compactor = ContextCompactor(1000)
    assert compactor.compact(messages) is None


def test_run_command_placeholder_keeps_exit_code_and_summary() -> None:
    text = "exit code: 1\n--- stdout ---\n" + "noise\n" * 500 + "2 failed, 3 passed\n--- stderr ---\n"
    stub = placeholder(ToolCall("c", "run_command", "{}"), text)
    assert "exit code: 1" in stub and "2 failed, 3 passed" in stub and "--- std" not in stub
    assert len(stub) < 500


def test_placeholder_limits_long_lines() -> None:
    stub = placeholder(ToolCall("c", "run_command", "{}"), "exit code: 1\n" + "L" * 50_000)
    assert len(stub) < 500


def test_other_tools_keep_no_output() -> None:
    stub = placeholder(ToolCall("c", "read_file", "{}"), "SECRET-LOOKING CONTENT\n" * 100)
    assert "SECRET-LOOKING" not in stub and "read_file" in stub


def test_error_flag_and_pairing_survive_for_claude() -> None:
    # Claude 要求每个 tool_use 都有对应的 tool_result：清理只换内容，id 和 is_error 不变
    messages = conversation(6)
    first = messages[3]
    assert isinstance(first, ToolResultMessage)
    messages[3] = ToolResultMessage(first.tool_call_id, first.content, is_error=True)
    compactor = ContextCompactor(6000)
    assert compactor.compact(messages) is not None
    _, converted = convert_messages(compactor.view(messages))
    block = converted[2]["content"][0]
    assert block["tool_use_id"] == "call_0" and block["is_error"] is True and "output cleared" in block["content"]


def test_native_blocks_are_passed_through_untouched() -> None:
    # 思考块必须一个字节不差地回传
    payload = [{"type": "thinking", "thinking": "t", "signature": "s"}, {"type": "tool_use", "id": "a", "name": "n",
                                                                         "input": {}}]
    messages: list[Message] = [SystemMessage("s"), UserMessage("t"), AssistantMessage(None, (ToolCall("a", "n", "{}"),),
                                                                                      Native("anthropic", payload))]
    messages.append(ToolResultMessage("a", BIG))
    messages.extend(conversation(8)[2:])
    compactor = ContextCompactor(10_000)
    assert compactor.compact(messages) is not None
    view = compactor.view(messages)
    assert view[2] is messages[2]


class SizedProvider(ScriptedProvider):
    """报告真实用量的假模型：用量等于这一轮看到的对话的估算。"""

    def complete(self, messages, tools, *, cancel=None):  # type: ignore[no-untyped-def]
        resp = super().complete(messages, tools, cancel=cancel)
        size = sum(message_tokens(m) for m in messages)
        return LLMResponse(resp.content, resp.tool_calls, Usage(prompt_tokens=size), resp.stop_reason, resp.native)


def _reads(n: int) -> list[LLMResponse]:
    return [*(LLMResponse(None, [call("read_file", path="big.txt")]) for _ in range(n)), LLMResponse("done")]


def test_agent_compacts_and_records_it(workspace: Path, settings: Settings) -> None:
    (workspace / "big.txt").write_text("line of text here\n" * 2000)
    llm = SizedProvider(_reads(12))
    custom = settings.model_copy(update={"context_compact_tokens": 12_000, "repo_map_chars": 0})
    result = Agent(llm, workspace, custom, runner=NoSandboxRunner()).run("x")
    events = result.trace.of("context_compact")
    assert events and events[0]["cleared_results"] >= 1 and events[0]["threshold"] == 12_000
    assert any(isinstance(m, ToolResultMessage) and "output cleared" in m.content for m in llm.seen[-1])
    summary = result.trace.summary()
    assert summary["compactions"] == len(events) and summary["cleared_tokens"] > 0 and events[0]["source"] == "client"
    # 上下文的峰值应该压在阈值附近，不压缩的话一路涨到 40000 以上
    assert summary["peak_prompt_tokens"] < 20_000


def test_agent_without_compaction_sends_everything(workspace: Path, settings: Settings) -> None:
    (workspace / "big.txt").write_text("line of text here\n" * 2000)
    llm = SizedProvider(_reads(12))
    custom = settings.model_copy(update={"context_compact_tokens": 0, "repo_map_chars": 0})
    result = Agent(llm, workspace, custom, runner=NoSandboxRunner()).run("x")
    assert result.trace.of("context_compact") == [] and result.trace.summary()["peak_prompt_tokens"] > 30_000
    assert not any(isinstance(m, ToolResultMessage) and "output cleared" in m.content for m in llm.seen[-1])
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage) and "output was cleared" not in system.content
