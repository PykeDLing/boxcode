"""macOS Seatbelt（sandbox-exec）沙盒。规则思路沿用 MacBox：

- 写：默认全部禁止，只放行工作区和系统临时目录；工作区里的 .git/hooks、.git/config 也不能改
  （改了 hook，下次你自己在沙盒外 git commit 时就会执行它）
- 读：挡住 SSH、GPG、云服务凭证、浏览器和其他 App 的数据，以及 BoxCode 自己的执行轨迹
- 套接字：连不上主目录里别的程序的套接字（gpg-agent、1Password SSH 代理、Docker）
- 网络：默认断网（连本机代理、域名解析一起挡），--allow-network 才放行

Seatbelt 按先后匹配，同一操作名后面的规则覆盖前面的。
"""

from pathlib import Path

from boxcode.sandbox.runner import CommandResult, run_process

SANDBOX_EXEC = "/usr/bin/sandbox-exec"

PRIVATE_READS = (
    ".ssh", ".gnupg", ".aws", ".kube", ".docker", ".netrc", ".git-credentials", ".npmrc", ".pypirc",
    ".config/gh", ".config/gcloud", ".zsh_history", ".bash_history", ".codex", ".claude", ".boxcode",
    "Library/Keychains", "Library/Mail", "Library/Messages", "Library/Safari", "Library/Cookies",
    "Library/Application Support", "Library/Containers", "Library/Group Containers", "Library/Mobile Documents",
)

SYSTEM_WRITABLE = ("/private/tmp", "/private/var/folders", "/dev")

OFFLINE_RULES = """
(deny network-outbound (remote ip))
(deny network-inbound (local ip))
(deny network-outbound (remote unix-socket (path-literal "/private/var/run/mDNSResponder")))
(deny mach-lookup (global-name "com.apple.dnssd.service"))
"""


def _q(path: str | Path) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def make_profile(workspace: Path, home: Path, allow_network: bool) -> str:
    ws = workspace.resolve()
    home = home.resolve()
    writable = "\n".join(f"  (subpath {_q(p)})" for p in (ws, *SYSTEM_WRITABLE))
    private = "\n".join(f"  (subpath {_q(home / p)})" for p in PRIVATE_READS)
    return f"""(version 1)
(allow default)

(deny file-write*)
(allow file-write*
{writable})
(deny file-write*
  (subpath {_q(ws / ".git" / "hooks")})
  (literal {_q(ws / ".git" / "config")}))

; 只挡内容读取，不挡元数据：程序启动时要逐级解析路径
(deny file-read-data
{private})

(deny network-outbound (remote unix-socket (subpath {_q(home)})))
(allow network-outbound (remote unix-socket (subpath {_q(ws)})))
(deny appleevent-send)
{"" if allow_network else OFFLINE_RULES}"""


class SeatbeltRunner:
    name = "seatbelt"

    def __init__(self, workspace: Path, allow_network: bool = False, home: Path | None = None) -> None:
        self.workspace = workspace.resolve()
        self.profile = make_profile(self.workspace, home or Path.home(), allow_network)

    def run(self, command: str, cwd: Path, timeout_s: int) -> CommandResult:
        return run_process([SANDBOX_EXEC, "-p", self.profile, "/bin/sh", "-c", command], cwd, timeout_s)
