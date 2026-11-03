"""执行轨迹：每一步一行 JSON。评测统计、失败归因、回放都从这里读。

事件类型：run_start、llm_call、tool_call、verify、run_end。
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any


class TraceRecorder:
    def __init__(self, runs_dir: Path | None) -> None:
        self.run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.events: list[dict[str, Any]] = []
        self.path: Path | None = None
        if runs_dir is not None:
            runs_dir.mkdir(parents=True, exist_ok=True)
            self.path = runs_dir / f"{self.run_id}.jsonl"

    def emit(self, event: str, **data: Any) -> None:
        record = {"ts": round(time.time(), 3), "run_id": self.run_id, "event": event, **data}
        self.events.append(record)
        if self.path is not None:
            with self.path.open("a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def of(self, event: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event"] == event]

    def summary(self) -> dict[str, Any]:
        llm = self.of("llm_call")
        tools = self.of("tool_call")
        return {
            "llm_calls": len(llm),
            "prompt_tokens": sum(e["prompt_tokens"] for e in llm),
            "completion_tokens": sum(e["completion_tokens"] for e in llm),
            "cached_tokens": sum(e.get("cached_tokens", 0) for e in llm),
            "llm_seconds": round(sum(e["latency_s"] for e in llm), 2),
            "tool_calls": len(tools),
            "tool_errors": sum(1 for e in tools if not e["ok"]),
            "denied": sum(1 for e in tools if e["decision"] == "deny"),
        }
