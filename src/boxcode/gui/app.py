"""桌面窗口：pywebview 把 static/ 里的页面装进原生 macOS 窗口（WKWebView）。

页面以 HTML 字符串直接加载，JavaScript 通过 window.expose 暴露的几个函数调 GuiApi，不在本机开 HTTP 端口：
开了端口，浏览器里随便一个网页都能往 127.0.0.1 发请求，替你发起一次 full-auto 的运行。

页面上显示的内容大多来自仓库（任务、工具参数、模型的回复），里面可能藏着注入的 HTML。
页面一律用 textContent 渲染；CSP 只放行带本次随机 nonce 的脚本，并且不许联网，
就算哪里漏了，注入的脚本也跑不起来、发不出数据。

窗口被导航到别的页面时，pywebview 会把接口再注入一遍（不看来源），所以还有两道：
页面拦掉拖放（拖进来的文件会被直接打开），每次调用都要带只写在我们页面里的 token（见 gui/api.py）。
"""

import json
import secrets
from importlib.resources import files
from pathlib import Path
from typing import Any

import webview

from boxcode.config import Settings
from boxcode.gui.api import GuiApi, bridge_functions


def page_html(token: str = "") -> str:
    static = files("boxcode.gui") / "static"
    nonce = secrets.token_urlsafe(16)
    # 先换模板变量再放进样式和脚本：它们的内容不会被当成模板。两个值都是 URL 安全的 base64，放进属性里不用转义
    html = static.joinpath("index.html").read_text(encoding="utf-8")
    html = html.replace("{{nonce}}", nonce).replace("{{token}}", token)
    html = html.replace("/*{{style}}*/", static.joinpath("app.css").read_text(encoding="utf-8"))
    return html.replace("/*{{script}}*/", static.joinpath("app.js").read_text(encoding="utf-8"))


def launch(settings: Settings, tasks_dir: Path, results_dir: Path, debug: bool = False) -> None:
    windows: list[webview.Window] = []

    def push(kind: str, data: dict[str, Any]) -> None:
        # run_js 原样执行，不经过 eval；参数是 JSON，本身就是合法的 JavaScript 字面量
        windows[0].run_js(f"window.boxcode.receive({json.dumps({'kind': kind, **data})})")

    def pick_folder() -> str | None:
        paths = windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return paths[0] if paths else None

    # 窗口里不许打开 file:// 页面：拖进来的 HTML 文件打不开，也就读不到本机文件
    webview.settings["ALLOW_FILE_URLS"] = False
    token = secrets.token_urlsafe(32)
    api = GuiApi(settings, tasks_dir, results_dir, push, pick_folder)
    window = webview.create_window(
        "BoxCode", html=page_html(token), js_api=None, width=1280, height=840, min_size=(1000, 640),
        text_select=True,
    )
    if window is None:
        raise RuntimeError("pywebview 没能创建窗口")
    window.expose(*bridge_functions(api, token))
    windows.append(window)
    try:
        webview.start(debug=debug)
    finally:
        api.shutdown()
