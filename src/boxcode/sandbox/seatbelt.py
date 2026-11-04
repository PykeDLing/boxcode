"""macOS Seatbelt（sandbox-exec）沙盒。规则思路沿用 MacBox，下面每一条都有 tests/test_sandbox.py 里的测试：

- 写：默认全部禁止，只放行工作区、系统临时目录和 /dev 里的几个文件（read-only 模式下工作区也不放行）
  - 任何位置的 .git 都只读（改了 hook、core.fsmonitor，或者把 .git 换成指向别处的文件，下次你在沙盒外运行 git
    就会执行它）。工作区和它的每一级上级目录本身也不能改名、删除：
    否则把工作区整个挪到 /tmp、改完 .git 再挪回来就绕过去了
- 读：挡住 SSH、GPG、云服务凭证、shell 配置和历史、浏览器和其他 App 的数据、工作区外的 .env，
  以及 BoxCode 自己的执行轨迹；这些位置如果是符号链接，链接指向的真实位置也挡。这是黑名单，工作区外的其他文件仍然读得到
- 进程间通信：只能连工作区和这个沙盒自己的临时目录里的 unix 套接字（别的程序的 ssh-agent、浏览器、Docker 都连不上）；
  不能通过 LaunchServices 打开程序（`open` 起来的程序不在沙盒里）、不能发 Apple 事件、不能写别的程序的偏好设置、
  不能读写剪贴板、不能找钥匙串服务、不能给沙盒外的进程发信号
- 网络：默认断网（连本机代理、域名解析一起挡），--allow-network 才放行
- 进程：每条命令的规则里带一个独一无二的标记（procs.py），命令结束时按标记找出沙盒里剩下的进程全部杀掉，
  用 setsid、setpgid 脱离了进程组的也跑不掉

Seatbelt 按先后匹配，同一操作名后面的规则覆盖前面的。
"""

import shutil
import tempfile
import threading
import weakref
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from boxcode.paths import canonical
from boxcode.sandbox.procs import marker_rule, new_marker
from boxcode.sandbox.runner import CommandResult, run_process

SANDBOX_EXEC = "/usr/bin/sandbox-exec"

PRIVATE_READS = (
    # 凭证
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".netrc", ".git-credentials", ".npmrc", ".pypirc",
    ".config/gh", ".config/gcloud", ".config/op", ".config/anthropic", ".config/github-copilot",
    ".config/git/credentials", ".cargo/credentials", ".cargo/credentials.toml", ".ollama",
    ".terraform.d", ".vault-token", ".pgpass", ".my.cnf", ".m2/settings.xml", ".gradle/gradle.properties",
    # shell 配置和历史：很多人把 API key 写在 .zshrc 里
    ".zshrc", ".zshenv", ".zprofile", ".zlogin", ".bashrc", ".bash_profile", ".profile", ".config/fish",
    ".zsh_history", ".zsh_sessions", ".bash_history", ".bash_sessions", ".local/share/fish",
    ".python_history", ".node_repl_history", ".psql_history",
    # 其他 Agent 和 BoxCode 自己的数据
    ".codex", ".claude", ".claude.json", ".gemini", ".cursor", ".boxcode",
    "Library/Keychains", "Library/Mail", "Library/Messages", "Library/Safari", "Library/Cookies",
    "Library/HTTPStorages", "Library/Application Support", "Library/Containers", "Library/Group Containers",
    "Library/Mobile Documents",
)

# 路径里任何一层叫 .git（大小写不敏感：APFS 默认不区分大小写）
GIT_DIR_REGEX = r'#"/\.[Gg][Ii][Tt](/|$)"'
# .env、.env.local、.envrc 这类文件
DOTENV_REGEX = r'#"/\.env(rc|\.[^/]*)?$"'

SYSTEM_WRITABLE = ("/private/tmp", "/private/var/folders")
SHORT_TMP = "/private/tmp"
# /dev 下面只放行这些：整个 /dev 可写的话，命令能往你别的终端（/dev/ttys*）里写转义序列
DEV_WRITABLE = ("/dev/null", "/dev/zero", "/dev/dtracehelper", "/dev/tty", "/dev/stdout", "/dev/stderr")
DEV_FD_REGEX = r'#"^/dev/fd/[0-9]+$"'

# 沙盒里不许找的系统服务：剪贴板（读走你复制过的东西）、钥匙串
DENIED_SERVICES = (
    "com.apple.pasteboard.1", "com.apple.SecurityServer", "com.apple.securityd.xpc", "com.apple.secd",
)

OFFLINE_RULES = """
(deny network-outbound (remote ip))
(deny network-inbound (local ip))
(deny mach-lookup (global-name "com.apple.dnssd.service"))
"""
# 联网时放行域名解析用的套接字（其他 unix 套接字照样不许连）
ONLINE_RULES = """
(allow network-outbound (remote unix-socket (path-literal "/private/var/run/mDNSResponder")))
"""


def _q(path: str | Path) -> str:
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _private_paths(home: Path) -> list[Path]:
    """要挡的位置，加上它们是符号链接时指向的真实位置（Seatbelt 按解析后的路径匹配）。"""
    out: list[Path] = []
    for rel in PRIVATE_READS:
        p = home / rel
        out.append(p)
        real = canonical(p)
        if real != p:
            out.append(real)
    return out


def _subpaths(paths: Iterable[Path | str]) -> str:
    return "\n".join(f"  (subpath {_q(p)})" for p in paths)


def make_profile(
    workspace: Path, home: Path, allow_network: bool, writable_workspace: bool = True,
    socket_dirs: Iterable[Path] = (),
) -> str:
    ws = canonical(workspace)
    home = canonical(home)
    writable = "\n".join([
        _subpaths((ws, *SYSTEM_WRITABLE)),
        *(f"  (literal {_q(p)})" for p in DEV_WRITABLE),
        f"  (regex {DEV_FD_REGEX})",
    ])
    # 工作区和每一级上级目录本身：不能改名、删除、换成别的东西（里面的文件照常能建、能删）
    pinned = "\n".join(f"  (literal {_q(p)})" for p in (ws, *ws.parents))
    # 不能只是不放行工作区：工作区可能就在 /private/tmp、/private/var/folders 下面（评测就是），要单独再禁止
    read_only = "" if writable_workspace else f"(deny file-write* (subpath {_q(ws)}))\n"
    sockets = "\n".join(f"(allow network-outbound (remote unix-socket (subpath {_q(p)})))"
                        for p in (ws, *socket_dirs))
    services = "\n".join(f"  (global-name {_q(s)})" for s in DENIED_SERVICES)
    return f"""(version 1)
(allow default)

(deny file-write*)
(allow file-write*
{writable})
(deny file-write* (regex {GIT_DIR_REGEX}))
(deny file-write*
{pinned})
{read_only}
; 只挡内容读取，不挡元数据：程序启动时要逐级解析路径
(deny file-read-data
{_subpaths(_private_paths(home))})
(deny file-read-data
  (require-all (regex {DOTENV_REGEX}) (require-not (subpath {_q(ws)}))))

(deny network-outbound (remote unix-socket))
{sockets}
(deny appleevent-send)
(deny lsopen)
(deny user-preference-write)
(deny mach-lookup
{services})
(deny signal)
(allow signal (target same-sandbox))
{ONLINE_RULES if allow_network else OFFLINE_RULES}"""


class SeatbeltRunner:
    name = "seatbelt"

    def __init__(
        self, workspace: Path, allow_network: bool = False, home: Path | None = None, writable: bool = True,
    ) -> None:
        self.workspace = canonical(workspace)
        # 这个沙盒自己的临时目录：命令的 TMPDIR 指向这里，只有这里和工作区的 unix 套接字连得上
        # （multiprocessing、asyncio 的测试会在 TMPDIR 里建套接字；系统 TMPDIR 里还有浏览器等程序的套接字，不能放行）。
        # 放在 /private/tmp 下、名字短：unix 套接字的路径最长 104 字节，系统 TMPDIR 太长，multiprocessing 会建不了
        self.tmpdir = canonical(Path(tempfile.mkdtemp(prefix="bx-", dir=SHORT_TMP)))
        weakref.finalize(self, shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.profile = make_profile(self.workspace, home or Path.home(), allow_network, writable,
                                    socket_dirs=(self.tmpdir,))

    def run(
        self, command: str, cwd: Path, timeout_s: float, *,
        cancel: threading.Event | None = None, env: Mapping[str, str] | None = None, pass_fds: Sequence[int] = (),
    ) -> CommandResult:
        # 每条命令一个标记：命令结束时按它找出沙盒里剩下的进程（包括脱离了进程组的）全部杀掉，
        # 同时在跑的别的命令（另一个 Agent、判分）有自己的标记，不会被误杀
        marker = new_marker()
        argv = [SANDBOX_EXEC, "-p", f"{self.profile}\n{marker_rule(marker)}\n", "/bin/sh", "-c", command]
        return run_process(argv, cwd, timeout_s, cancel=cancel, env={"TMPDIR": f"{self.tmpdir}/", **(env or {})},
                           sandbox_marker=marker, pass_fds=pass_fds)
