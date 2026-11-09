"""执行轨迹：每一步一行 JSON。评测统计、失败归因、回放都从这里读。

事件类型：run_start、repo_map、context_compact、llm_call、llm_error、tool_call、plan_update、hook_error、verify、run_end。

写文件失败（磁盘满了、目录被删）不抛异常：事件照样留在内存里、照样推给界面，第一次的错误记在 write_error 里。
轨迹是旁路记录，不能因为它让一次运行崩掉。
"""

import json
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

Listener = Callable[[dict[str, Any]], None]


class TraceRecorder:
    def __init__(self, runs_dir: Path | None, listener: Listener | None = None) -> None:
        self.run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.events: list[dict[str, Any]] = []
        self.path: Path | None = None
        self.write_error: str | None = None
        # 每记一条事件就调用一次：桌面界面用它实时显示执行过程
        self.listener = listener
        if runs_dir is not None:
            self.path = runs_dir / f"{self.run_id}.jsonl"
            try:
                runs_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                self.write_error = f"{type(e).__name__}: {e}"

    def emit(self, event: str, **data: Any) -> None:
        record = {"ts": round(time.time(), 3), "run_id": self.run_id, "event": event, **data}
        self.events.append(record)
        if self.path is not None:
            try:
                # backslashreplace：模型给的参数里可能有单独的代理字符，写出来是 JSON 里合法的 \udc80，不会抛异常
                with self.path.open("a", encoding="utf-8", errors="backslashreplace") as f:
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            except OSError as e:
                self.write_error = self.write_error or f"{type(e).__name__}: {e}"
        if self.listener is not None:
            self.listener(record)

    def of(self, event: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event"] == event]

    def summary(self) -> dict[str, Any]:
        llm = self.of("llm_call")
        tools = self.of("tool_call")
        compactions = self.of("context_compact")
        return {
            "llm_calls": len(llm),
            "prompt_tokens": sum(e["prompt_tokens"] for e in llm),
            "peak_prompt_tokens": max((e["prompt_tokens"] for e in llm), default=0),
            "completion_tokens": sum(e["completion_tokens"] for e in llm),
            "cached_tokens": sum(e.get("cached_tokens", 0) for e in llm),
            "llm_seconds": round(sum(e["latency_s"] for e in llm), 2),
            "tool_calls": len(tools),
            "tool_errors": sum(1 for e in tools if not e["ok"]),
            "denied": sum(1 for e in tools if e["decision"] == "deny"),
            "compactions": len(compactions),
            "cleared_tokens": sum(e["cleared_tokens"] for e in compactions),
            "plan_updates": len(self.of("plan_update")),
        }


def read_trace(path: Path) -> list[dict[str, Any]]:
    """读回一次运行的全部事件。写了一半的行（进程中途被杀）跳过。"""
    events = []
    # 只按 \n 分行：JSON 里的 U+2028 是原样写的，splitlines() 会在那里把一条事件切成两半
    for line in path.read_text(errors="replace").split("\n"):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            events.append(record)
    return events
