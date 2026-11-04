"""macOS Seatbelt（sandbox-exec）沙盒。规则思路沿用 MacBox：

- 写：默认全部禁止，只放行工作区和系统临时目录（read-only 模式下工作区也不放行）；工作区里任何一层的 .git 都只读
  （改了 hook、core.fsmonitor，或者把 .git 换成指向别处的文件，下次你在沙盒外运行 git 就会执行它）
- 读：挡住 SSH、GPG、云服务凭证、shell 配置和历史、浏览器和其他 App 的数据、工作区外的 .env，
  以及 BoxCode 自己的执行轨迹。这是黑名单，工作区外的其他文件仍然读得到
- 套接字：连不上主目录里别的程序的套接字（gpg-agent、1Password SSH 代理、Docker）
- 网络：默认断网（连本机代理、域名解析一起挡），--allow-network 才放行

Seatbelt 按先后匹配，同一操作名后面的规则覆盖前面的。
"""

from pathlib import Path

from boxcode.sandbox.runner import CommandResult, run_process

SANDBOX_EXEC = "/usr/bin/sandbox-exec"

PRIVATE_READS = (
    # 凭证
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".netrc", ".git-credentials", ".npmrc", ".pypirc",
    ".config/gh", ".config/gcloud", ".config/op", ".cargo/credentials", ".cargo/credentials.toml",
    ".terraform.d", ".vault-token", ".pgpass", ".my.cnf", ".m2/settings.xml", ".gradle/gradle.properties",
    # shell 配置和历史：很多人把 API key 写在 .zshrc 里
    ".zshrc", ".zshenv", ".zprofile", ".zlogin", ".bashrc", ".bash_profile", ".profile", ".config/fish",
    ".zsh_history", ".zsh_sessions", ".bash_history", ".bash_sessions", ".local/share/fish",
    ".python_history", ".node_repl_history", ".psql_history",
    # 其他 Agent 和 BoxCode 自己的数据
    ".codex", ".claude", ".boxcode",
    "Library/Keychains", "Library/Mail", "Library/Messages", "Library/Safari", "Library/Cookies",
    "Library/Application Support", "Library/Containers", "Library/Group Containers", "Library/Mobile Documents",
)

# 路径里任何一层叫 .git（大小写不敏感：APFS 默认不区分大小写）
GIT_DIR_REGEX = r'#"/\.[Gg][Ii][Tt](/|$)"'
# .env、.env.local、.envrc 这类文件
DOTENV_REGEX = r'#"/\.env(rc|\.[^/]*)?$"'

SYSTEM_WRITABLE = ("/private/tmp", "/private/var/folders", "/dev")

OFFLINE_RULES = """
(deny network-outbound (remote ip))
(deny network-inbound (local ip))
(deny network-outbound (remote unix-socket (path-literal "/private/var/run/mDNSResponder")))
(deny mach-lookup (global-name "com.apple.dnssd.service"))
"""


def _q(path: str | Path) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def make_profile(workspace: Path, home: Path, allow_network: bool, writable_workspace: bool = True) -> str:
    ws = workspace.resolve()
    home = home.resolve()
    writable = "\n".join(f"  (subpath {_q(p)})" for p in (ws, *SYSTEM_WRITABLE))
    private = "\n".join(f"  (subpath {_q(home / p)})" for p in PRIVATE_READS)
    # 不能只是不放行工作区：工作区可能就在 /private/tmp、/private/var/folders 下面（评测就是），要单独再禁止
    read_only = "" if writable_workspace else f"(deny file-write* (subpath {_q(ws)}))\n"
    return f"""(version 1)
(allow default)

(deny file-write*)
(allow file-write*
{writable})
(deny file-write*
  (require-all (subpath {_q(ws)}) (regex {GIT_DIR_REGEX})))
{read_only}
; 只挡内容读取，不挡元数据：程序启动时要逐级解析路径
(deny file-read-data
{private})
(deny file-read-data
  (require-all (regex {DOTENV_REGEX}) (require-not (subpath {_q(ws)}))))

(deny network-outbound (remote unix-socket (subpath {_q(home)})))
(allow network-outbound (remote unix-socket (subpath {_q(ws)})))
(deny appleevent-send)
{"" if allow_network else OFFLINE_RULES}"""


class SeatbeltRunner:
    name = "seatbelt"

    def __init__(
        self, workspace: Path, allow_network: bool = False, home: Path | None = None, writable: bool = True,
    ) -> None:
        self.workspace = workspace.resolve()
        self.profile = make_profile(self.workspace, home or Path.home(), allow_network, writable)

    def run(self, command: str, cwd: Path, timeout_s: int) -> CommandResult:
        return run_process([SANDBOX_EXEC, "-p", self.profile, "/bin/sh", "-c", command], cwd, timeout_s)
