"""工具的公共部分：参数用 Pydantic 声明，自动生成给模型的 JSON Schema。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel

from boxcode.config import Settings
from boxcode.sandbox import SandboxRunner


class Risk(StrEnum):
    READ = "read"  # 只读工作区
    WRITE = "write"  # 改工作区里的文件
    EXEC = "exec"  # 在沙盒里执行命令


class ToolError(Exception):
    """工具执行失败，原因会作为工具结果回给模型，让它自己调整。"""


@dataclass(frozen=True)
class ToolContext:
    workspace: Path
    runner: SandboxRunner
    settings: Settings


@dataclass(frozen=True)
class ToolResult:
    text: str
    ok: bool = True


@dataclass(frozen=True)
class Target:
    """这次调用会碰到什么，给权限策略判断用。"""

    paths: list[Path] = field(default_factory=list)
    command: str | None = None


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    risk: ClassVar[Risk]
    Params: ClassVar[type[BaseModel]]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.Params.model_json_schema(),
            },
        }

    def target(self, ctx: ToolContext, params: BaseModel) -> Target:
        path = getattr(params, "path", None)
        return Target(paths=[resolve_in_workspace(ctx.workspace, path)] if path is not None else [])

    @abstractmethod
    def run(self, ctx: ToolContext, params: Any) -> ToolResult: ...


def in_workspace(workspace: Path, p: Path) -> bool:
    """解析链接后是否仍在工作区里。"""
    rp = p.resolve()
    ws = workspace.resolve()
    return rp == ws or ws in rp.parents


def resolve_in_workspace(workspace: Path, path: str) -> Path:
    """相对路径按工作区解析；解析链接后必须仍在工作区里，否则拒绝（防止 ../ 和指向外面的链接）。"""
    p = (workspace / path).resolve()
    if not in_workspace(workspace, p):
        raise ToolError(f"路径不在工作区内：{path}")
    return p


def truncate(text: str, limit: int) -> str:
    """保留开头和结尾：报错信息常在最后。"""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n\n... [省略 {len(text) - limit} 个字符] ...\n\n{text[-half:]}"
