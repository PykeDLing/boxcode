"""权限策略：每次工具调用执行前先问它，结果是放行、问用户、拒绝三种之一。

它只是第一道关：命令可以拼接、编码、换写法，正则拦不全。真正的边界是沙盒，
策略的作用是把高风险的事提前拿出来给人看，并在执行轨迹里留下“为什么放行/拒绝”。
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from boxcode.tools.base import Risk, Target


class ApprovalMode(StrEnum):
    READ_ONLY = "read-only"  # 只能读；写文件拒绝，执行命令要问
    WORKSPACE_WRITE = "workspace-write"  # 默认：读写工作区、沙盒里执行；高风险命令要问
    FULL_AUTO = "full-auto"  # 全部放行（仍在沙盒里），评测时用


class Action(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


# 工作区里也不许改的位置：改了 git hook，下次你在沙盒外 git commit 就会执行它
PROTECTED = (".git/hooks", ".git/config")

# 要先问人的命令
RISKY_COMMANDS: tuple[tuple[str, str], ...] = (
    (r"\b(curl|wget|nc|ssh|scp)\b", "联网或远程访问"),
    (r"\bgit\s+(push|remote|config)\b", "改动远程仓库或 git 配置"),
    (r"\b(pip|uv\s+pip|npm|pnpm|yarn|brew)\s+(install|add|i)\b", "安装依赖"),
    (r"\brm\s+-\w*r", "递归删除"),
    (r"\b(sudo|chmod\s+-R|chown)\b", "改权限或提权"),
    (r"(base64\s+-d|\|\s*(sh|bash|zsh|python3?)\b)", "执行解码或下载来的内容"),
)


class Policy:
    def __init__(self, mode: ApprovalMode, workspace: Path) -> None:
        self.mode = mode
        self.workspace = workspace.resolve()

    def check(self, risk: Risk, target: Target) -> Decision:
        if risk is Risk.READ:
            return Decision(Action.ALLOW, "只读工作区")

        if risk is Risk.WRITE:
            if self.mode is ApprovalMode.READ_ONLY:
                return Decision(Action.DENY, "只读模式不能写文件")
            for p in target.paths:
                rel = p.relative_to(self.workspace).as_posix()
                if any(rel == q or rel.startswith(q + "/") for q in PROTECTED):
                    return Decision(Action.DENY, f"受保护的位置：{rel}")
            return Decision(Action.ALLOW, "写工作区内的文件")

        # Risk.EXEC
        command = target.command or ""
        if self.mode is ApprovalMode.FULL_AUTO:
            return Decision(Action.ALLOW, "full-auto 模式，在沙盒中执行")
        if self.mode is ApprovalMode.READ_ONLY:
            return Decision(Action.ASK, "只读模式下执行命令需要确认")
        for pattern, why in RISKY_COMMANDS:
            if re.search(pattern, command):
                return Decision(Action.ASK, f"高风险命令（{why}）")
        return Decision(Action.ALLOW, "在沙盒中执行")
