"""OpenAI 兼容接口的格式转换和回复解析。

前一半不发请求：把 SDK 的 create 换成返回固定回复的函数。流式那一半另外起一个本机的假服务器，
走真的 SDK 和真的连接：按停止时连接有没有断开，只有这样才看得出来。
"""

import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import openai
import pytest
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from boxcode.agent import Agent, Status
from boxcode.config import Settings, Thinking
from boxcode.llm.base import (
    AssistantMessage,
    LLMCancelled,
    LLMUnavailable,
    Native,
    StopReason,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    UserMessage,
)
from boxcode.llm.openai_compat import OpenAICompatProvider, convert_messages, convert_tools, read_stream
from boxcode.sandbox import NoSandboxRunner


def test_messages_converted_and_native_content_dropped() -> None:
    out = convert_messages([
        SystemMessage("SYS"), UserMessage("task"),
        AssistantMessage(None, (ToolCall("c1", "grep", '{"pattern":"a"}'),), native=Native("anthropic", ["thinking"])),
        ToolResultMessage("c1", "hit", is_error=True),
    ])
    assert out == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "grep", "arguments": '{"pattern":"a"}'}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "hit"},
    ]
    assert convert_tools([ToolSpec("t", "d", {"type": "object"})]) == [
        {"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}]


def completion(finish_reason: str, usage: dict[str, Any] | None = None, **message: Any) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": finish_reason,
                     "message": {"role": "assistant", "content": None, **message}}],
        "usage": usage,
    })


def provider(monkeypatch: pytest.MonkeyPatch, reply: ChatCompletion) -> OpenAICompatProvider:
    p = OpenAICompatProvider(Settings(api_key="k", stream=False))  # 这一半测的是不用流式时整条回复的解析
    monkeypatch.setattr(p._client.chat.completions, "create", lambda **_: reply)
    return p


def test_tool_calls_and_cached_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = completion("tool_calls", {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
                                      "prompt_tokens_details": {"cached_tokens": 64}},
                       tool_calls=[{"id": "c1", "type": "function", "function": {"name": "grep", "arguments": "{}"}}])
    r = provider(monkeypatch, reply).complete([UserMessage("x")], [])
    assert r.tool_calls == [ToolCall("c1", "grep", "{}")] and r.stop_reason is StopReason.END
    assert (r.usage.prompt_tokens, r.usage.completion_tokens, r.usage.cached_tokens) == (100, 7, 64)


def test_deepseek_cache_field(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = completion("stop", {"prompt_tokens": 50, "completion_tokens": 1, "total_tokens": 51,
                                "prompt_cache_hit_tokens": 32}, content="hi")
    r = provider(monkeypatch, reply).complete([UserMessage("x")], [])
    assert r.content == "hi" and r.usage.cached_tokens == 32


def test_length_means_truncated_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    # 以前只有 Claude 会把撞上输出上限的工具调用拦下来，OpenAI 兼容接口照样执行半截参数
    reply = completion("length", tool_calls=[
        {"id": "c1", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "a", "con'}}])
    r = provider(monkeypatch, reply).complete([UserMessage("x")], [])
    assert r.stop_reason is StopReason.MAX_TOKENS and r.truncated


def test_content_filter_is_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    r = provider(monkeypatch, completion("content_filter")).complete([UserMessage("x")], [])
    assert r.stop_reason is StopReason.REFUSAL


def test_thinking_disabled_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    # 小米 MiMo 默认开思考，不回传 reasoning_content 会报 400：能在请求里关掉。默认不带这个参数
    sent: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> ChatCompletion:
        sent.append(kwargs)
        return completion("stop", content="ok")

    options: tuple[Thinking, ...] = ("default", "disabled")
    for thinking in options:
        p = OpenAICompatProvider(Settings(api_key="k", thinking=thinking, stream=False))
        monkeypatch.setattr(p._client.chat.completions, "create", create)
        p.complete([UserMessage("x")], [])
    assert [k["extra_body"] for k in sent] == [None, {"thinking": {"type": "disabled"}}]


def test_missing_key_and_empty_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(LLMUnavailable, match="BOXCODE_API_KEY"):
        OpenAICompatProvider(Settings())
    empty = completion("stop").model_copy(update={"choices": []})
    with pytest.raises(LLMUnavailable, match="choices"):
        provider(monkeypatch, empty).complete([UserMessage("x")], [])


# ---- 流式 ----

def chunk(finish_reason: str | None = None, usage: dict[str, Any] | None = None, **delta: Any) -> dict[str, Any]:
    return {"id": "x", "object": "chat.completion.chunk", "created": 0, "model": "m", "usage": usage,
            "choices": [{"index": 0, "finish_reason": finish_reason, "delta": delta}]}


def tool_part(index: int, arguments: str, call_id: str | None = None, name: str | None = None) -> dict[str, Any]:
    return {"index": index, "id": call_id, "type": "function" if call_id else None,
            "function": {"name": name, "arguments": arguments}}


USAGE = {"prompt_tokens": 100, "completion_tokens": 7, "total_tokens": 107,
         "prompt_tokens_details": {"cached_tokens": 64}}
# 一条完整的流式回复：一段文字，两个工具调用（参数切成几段、两个调用的段落交错着到），最后单独一块 usage
REPLY = [
    chunk(role="assistant", content="先看"),
    chunk(content="一下"),
    chunk(tool_calls=[tool_part(0, "", "c1", "grep")]),
    chunk(tool_calls=[tool_part(0, '{"patt')]),
    chunk(tool_calls=[tool_part(1, '{"path": ', "c2", "read_file")]),
    chunk(tool_calls=[tool_part(0, 'ern": "a"}'), tool_part(1, '"a.py"}')]),
    chunk("tool_calls"),
    {**chunk(), "choices": [], "usage": USAGE},
]


def parsed(chunks: list[dict[str, Any]]) -> list[ChatCompletionChunk]:
    return [ChatCompletionChunk.model_validate(c) for c in chunks]


def test_stream_pieces_are_joined() -> None:
    r = read_stream(parsed(REPLY), None)
    assert r.content == "先看一下" and r.stop_reason is StopReason.END
    assert r.tool_calls == [ToolCall("c1", "grep", '{"pattern": "a"}'), ToolCall("c2", "read_file", '{"path": "a.py"}')]
    assert (r.usage.prompt_tokens, r.usage.completion_tokens, r.usage.cached_tokens) == (100, 7, 64)


def test_stream_stop_reasons() -> None:
    half = chunk(tool_calls=[tool_part(0, '{"path": "a", "con', "c1", "write_file")])
    cut = read_stream(parsed([half, chunk("length")]), None)
    assert cut.stop_reason is StopReason.MAX_TOKENS and cut.truncated  # 半截参数不会被执行
    assert read_stream(parsed([chunk("content_filter")]), None).stop_reason is StopReason.REFUSAL
    refused = read_stream(parsed([chunk(refusal="不能"), chunk(refusal="帮这个忙"), chunk("stop")]), None)
    assert refused.stop_reason is StopReason.REFUSAL and refused.content is None
    # 有的接口把 usage 放在带 finish_reason 的那一块里，没有单独的一块
    assert read_stream(parsed([chunk("stop", USAGE, content="ok")]), None).usage.prompt_tokens == 100


def test_stream_that_ends_early_is_an_error() -> None:
    # 连接中途断了：工具参数只到了一半，不能当成完整的回复
    with pytest.raises(LLMUnavailable, match="没有收完"):
        read_stream(parsed(REPLY[:4]), None)
    with pytest.raises(LLMUnavailable, match="choices"):
        read_stream(parsed([REPLY[-1]]), None)
    with pytest.raises(LLMUnavailable, match="choices"):
        read_stream([], None)


def test_cancel_stops_reading_the_stream() -> None:
    cancel = threading.Event()
    taken = 0

    def chunks() -> Iterator[ChatCompletionChunk]:
        nonlocal taken
        for c in parsed(REPLY):
            taken += 1
            if taken == 3:
                cancel.set()  # 第 3 块到的时候用户按了停止
            yield c

    with pytest.raises(LLMCancelled):
        read_stream(chunks(), cancel)
    assert taken == 3  # 后面的不再读


class Server:
    """本机的假接口：POST 过来就按 reply 写回 SSE。记下收到的请求，和客户端是不是中途断开了。"""

    def __init__(self, reply: Callable[["Server", Callable[[dict[str, Any] | str], None]], None]) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []
        self.sent = 0
        self.some_sent = threading.Event()
        self.disconnected = threading.Event()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                server.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()  # HTTP/1.0，不带 Content-Length：写完关连接就是结束

                def send(data: dict[str, Any] | str) -> None:
                    body = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
                    self.wfile.write(f"data: {body}\n\n".encode())
                    self.wfile.flush()
                    server.sent += 1

                try:
                    server.reply(server, send)
                except (BrokenPipeError, ConnectionResetError):
                    server.disconnected.set()

            def log_message(self, *_: Any) -> None:
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def provider(self) -> OpenAICompatProvider:
        return OpenAICompatProvider(Settings(api_key="k", model="m",
                                             base_url=f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"))

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Server]]:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)  # 本机设了代理的话，发给 127.0.0.1 的请求不能绕出去
    servers: list[Server] = []

    def start(reply: Callable[[Server, Callable[[dict[str, Any] | str], None]], None]) -> Server:
        servers.append(Server(reply))
        return servers[-1]

    yield start
    for server in servers:
        server.close()


def test_streaming_request_over_a_real_connection(serve: Callable[..., Server]) -> None:
    def reply(_: Server, send: Callable[[dict[str, Any] | str], None]) -> None:
        for c in REPLY:
            send(c)
        send("[DONE]")

    server = serve(reply)
    r = server.provider().complete([UserMessage("x")], [ToolSpec("grep", "d", {"type": "object"})])
    assert r.content == "先看一下" and [c.name for c in r.tool_calls] == ["grep", "read_file"]
    assert r.usage.cached_tokens == 64
    (request,) = server.requests
    assert request["stream"] is True and request["stream_options"] == {"include_usage": True}
    assert request["model"] == "m" and request["tools"][0]["function"]["name"] == "grep"
    # 没有工具时请求里不带 tools：空列表在真实接口上是 400（用 Claude 的兼容接口实测的）
    server.provider().complete([UserMessage("x")], [])
    assert "tools" not in server.requests[1]


def test_stop_closes_the_connection_mid_stream(serve: Callable[..., Server]) -> None:
    # 路线图第 10 步要的就是这个：按了停止，连接断开，服务器不再往下生成（也就不再计费）
    total = 400

    def reply(server: Server, send: Callable[[dict[str, Any] | str], None]) -> None:
        for _ in range(total):  # 一直出字，20 秒才写得完
            send(chunk(content="字"))
            if server.sent == 3:
                server.some_sent.set()
            threading.Event().wait(0.05)
        send(chunk("stop"))

    server = serve(reply)
    cancel = threading.Event()

    def press_stop() -> None:
        server.some_sent.wait(10)
        cancel.set()

    threading.Thread(target=press_stop, daemon=True).start()
    with pytest.raises(LLMCancelled):
        server.provider().complete([UserMessage("x")], [], cancel=cancel)
    assert server.disconnected.wait(10), "服务器没有发现连接断开"
    assert 3 <= server.sent < 40  # 断开之后服务器最多再写出去一两块


def test_stopping_an_agent_run_drops_the_model_connection(serve: Callable[..., Server], workspace: Path,
                                                          settings: Settings) -> None:
    # 同一件事经过主循环再走一遍：Agent 在后台线程里调模型，按停止后它不等那个线程，连接要靠 Provider 自己断开
    def reply(server: Server, send: Callable[[dict[str, Any] | str], None]) -> None:
        for _ in range(400):
            send(chunk(content="字"))
            server.some_sent.set()
            threading.Event().wait(0.05)
        send(chunk("stop"))

    server = serve(reply)
    cancel = threading.Event()
    agent = Agent(server.provider(), workspace, settings, runner=NoSandboxRunner(), cancel=cancel)

    def press_stop() -> None:
        server.some_sent.wait(10)
        cancel.set()

    threading.Thread(target=press_stop, daemon=True).start()
    assert agent.run("x").status is Status.CANCELLED
    assert server.disconnected.wait(10) and server.sent < 40


def test_connection_dropped_mid_stream_is_unavailable(serve: Callable[..., Server]) -> None:
    def reply(_: Server, send: Callable[[dict[str, Any] | str], None]) -> None:
        for c in REPLY[:4]:
            send(c)  # 写到一半服务器把连接关了

    with pytest.raises(LLMUnavailable, match="没有收完"):
        serve(reply).provider().complete([UserMessage("x")], [])


def test_garbage_in_the_stream_is_unavailable(serve: Callable[..., Server]) -> None:
    def reply(_: Server, send: Callable[[dict[str, Any] | str], None]) -> None:
        send(REPLY[0])
        send("{不是 JSON")

    with pytest.raises(LLMUnavailable, match="解析不了"):
        serve(reply).provider().complete([UserMessage("x")], [])


def test_stream_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    # 有的兼容接口流式的工具调用不完整：BOXCODE_STREAM=false 退回一次拿整条回复
    sent: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> ChatCompletion:
        sent.append(kwargs)
        return completion("stop", content="ok")

    p = OpenAICompatProvider(Settings.from_env({"BOXCODE_API_KEY": "k", "BOXCODE_STREAM": "false"}))
    monkeypatch.setattr(p._client.chat.completions, "create", create)
    assert p.complete([UserMessage("x")], []).content == "ok"
    assert "stream" not in sent[0] and "stream_options" not in sent[0]
    assert sent[0]["tools"] is openai.omit
