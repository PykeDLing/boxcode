"""权限策略：每次工具调用执行前先问它，结果是放行、问用户、拒绝三种之一。

它只是第一道关：命令可以拼接、编码、换写法，正则拦不全。真正的边界是沙盒，
策略的作用是把高风险的事提前拿出来给人看，并在执行轨迹里留下“为什么放行/拒绝”。
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from boxcode.paths import canonical, is_inside
from boxcode.sandbox import SandboxRunner, default_runner
from boxcode.sandbox.seatbelt import PRIVATE_READS
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


# 不能当工作区的系统目录（含它们下面的目录）：沙盒放行整个工作区的写入，/Applications、/opt/homebrew
# 这些地方普通用户也能写，改了里面的程序，你下次在沙盒外运行它就会执行
SYSTEM_DIRS = ("/Applications", "/Library", "/System", "/usr", "/bin", "/sbin", "/etc", "/private/etc", "/opt")
# 主目录里沙盒照常能读、但不能整个交给模型写的位置：里面的配置和程序之后会在沙盒外执行
# （~/.config/git/config 的 core.fsmonitor、fish 的 config.fish、~/.local/bin 里的命令）
HOME_EXEC_DIRS = (
    ".config", ".local", "bin", "go", ".oh-my-zsh", ".nvm", ".pyenv", ".rbenv", ".bun", ".deno", ".ipython", ".vim",
    ".hammerspoon",
)


class UnsafeWorkspace(ValueError):
    """工作区选在了沙盒不该放行写入的位置。"""


def check_workspace(workspace: Path, boxcode_home: Path, home: Path | None = None) -> None:
    """沙盒放行整个工作区的写入，所以工作区不能是这些地方：

    - 根目录、主目录和它们之间的目录：等于把 ~/.zshrc、~/Library/LaunchAgents 都交给了模型
    - 主目录里放凭证和其他 App 数据的位置（沙盒本来不让读的那些）、~/Library、HOME_EXEC_DIRS，
      以及包含它们的目录（例如 ~/.cargo 包含 ~/.cargo/credentials）
    - BoxCode 自己的数据目录（执行轨迹），或者包含它的目录
    - SYSTEM_DIRS 里的系统目录
    """
    # 换成磁盘上真实的大小写再比，并且比较时不区分大小写：APFS 上 /users/PYKE 就是主目录
    ws = canonical(workspace)
    home = canonical(home or Path.home())
    data = canonical(boxcode_home)

    inside = is_inside
    if inside(home, ws):  # 工作区是主目录，或者是它的上级目录
        raise UnsafeWorkspace(f"工作区不能是根目录、主目录或它们之间的目录：{ws}。选一个具体的项目目录")
    if inside(ws, data) or inside(data, ws):
        raise UnsafeWorkspace(f"工作区不能包含 BoxCode 的数据目录 {data}，也不能在它里面")
    home_roots = [home / "Library", *(home / p for p in (*PRIVATE_READS, *HOME_EXEC_DIRS))]
    for root in (*home_roots, *map(Path, SYSTEM_DIRS)):
        if inside(ws, root):
            raise UnsafeWorkspace(f"工作区不能放在 {root} 里：{ws}")
    for root in home_roots:
        if inside(root, ws):
            raise UnsafeWorkspace(f"工作区不能包含 {root}：{ws}")


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
RISKY_COMMANDS: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p), why) for p, why in (
    (r"\b(curl|wget|nc|ncat|ssh|scp|sftp|rsync|ftp|telnet|nscurl)\b", "联网或远程访问"),
    # git -C . push、git -c k=v push 也算
    (r"\bgit(\s+-[Cc]\s+\S+|\s+--?[\w-]+(=\S+)?)*\s+(push|remote|config)\b", "改动远程仓库或 git 配置"),
    (r"\b(pip3?(\.\d+)?|pipx|uv|npm|pnpm|yarn|bun|brew|poetry|cargo|gem|go)\s+(pip\s+)?(install|add|i|ci|sync)\b"
     r"|\bpython3?\s+-m\s+pip\s+install\b|\b(npx|uvx|bunx|pnpx)\s|\buv\s+run\s+(\S+\s+)*--with\b", "安装依赖"),
    # -r、-R、-rf、-f -r、--recursive 都算
    (r"\brm\s+(-\w+\s+)*(-\w*[rR]\w*|--recursive)\b|\bfind\b.*\s-delete\b|\bgit\s+clean\b", "递归删除"),
    (r"\b(sudo|chown)\b|\bchmod\s+(-\w+\s+)*-\w*R", "改权限或提权"),
    (r"base64\s+(-\w*[dD]\w*|--decode)\b|\|\s*(\S*/)?(env\s+)?(sh|bash|zsh|dash|python3?|perl|ruby|node)\b"
     r"|\beval\s", "执行解码或下载来的内容"),
))


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
            if pattern.search(command):
                return Decision(Action.ASK, f"高风险命令（{why}）")
        return Decision(Action.ALLOW, "在沙盒中执行")
