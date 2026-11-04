"""权限策略：每次工具调用执行前先问它，结果是放行、问用户、拒绝三种之一。

它只是第一道关：命令可以拼接、编码、换写法，正则拦不全。真正的边界是沙盒，
策略的作用是把高风险的事提前拿出来给人看，并在执行轨迹里留下“为什么放行/拒绝”。
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from boxcode.sandbox import SandboxRunner, default_runner
from boxcode.tools.base import Risk, Target


class ApprovalMode(StrEnum):
    READ_ONLY = "read-only"  # 只能读；写文件拒绝，执行命令要问，问过了也在只读沙盒里执行
    WORKSPACE_WRITE = "workspace-write"  # 默认：读写工作区、沙盒里执行；高风险命令要问
    FULL_AUTO = "full-auto"  # 全部放行（仍在沙盒里），评测时用


@dataclass(frozen=True)
class ExecutionPolicy:
    """一次运行的执行权限。权限策略、沙盒规则、系统提示都从这一个对象推出来，不会各说各的。"""

    mode: ApprovalMode = ApprovalMode.WORKSPACE_WRITE
    allow_network: bool = False
    sandboxed: bool = True  # False 就是 --dangerously-no-sandbox

    @property
    def workspace_writable(self) -> bool:
        return self.mode is not ApprovalMode.READ_ONLY

    def make_runner(self, workspace: Path) -> SandboxRunner:
        return default_runner(workspace, allow_network=self.allow_network, writable=self.workspace_writable,
                              no_sandbox=not self.sandboxed)


class Action(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


# 工作区里也不许改的位置：任何一层的 .git。改了 hook、core.fsmonitor，或者把 .git 换成指向别处的文件，
# 下次你在沙盒外运行 git 就会执行攻击者的命令。APFS 默认不区分大小写，.GIT/HOOKS 也是同一个目录
PROTECTED_DIR = ".git"

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
                rel = p.relative_to(self.workspace)
                if any(part.casefold() == PROTECTED_DIR for part in rel.parts):
                    return Decision(Action.DENY, f"受保护的位置：{rel.as_posix()}")
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
