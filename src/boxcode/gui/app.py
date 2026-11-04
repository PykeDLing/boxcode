"""桌面窗口：pywebview 把 static/ 里的页面装进原生 macOS 窗口（WKWebView）。

页面以 HTML 字符串直接加载，JavaScript 通过 pywebview 的 js_api 调 GuiApi，不在本机开 HTTP 端口：
开了端口，浏览器里随便一个网页都能往 127.0.0.1 发请求，替你发起一次 full-auto 的运行。

页面上显示的内容大多来自仓库（任务、工具参数、模型的回复），里面可能藏着注入的 HTML。
页面一律用 textContent 渲染；CSP 只放行带本次随机 nonce 的脚本，并且不许联网，
就算哪里漏了，注入的脚本也跑不起来、发不出数据。
"""

import json
import secrets
from importlib.resources import files
from pathlib import Path
from typing import Any

import webview

from boxcode.config import Settings
from boxcode.gui.api import GuiApi


def page_html() -> str:
    static = files("boxcode.gui") / "static"
    nonce = secrets.token_urlsafe(16)
    # 先换 nonce 再放进样式和脚本：它们的内容不会被当成模板
    html = static.joinpath("index.html").read_text(encoding="utf-8").replace("{{nonce}}", nonce)
    html = html.replace("/*{{style}}*/", static.joinpath("app.css").read_text(encoding="utf-8"))
    return html.replace("/*{{script}}*/", static.joinpath("app.js").read_text(encoding="utf-8"))


def launch(tasks_dir: Path, results_dir: Path, debug: bool = False) -> None:
    windows: list[webview.Window] = []

    def push(kind: str, data: dict[str, Any]) -> None:
        # run_js 原样执行，不经过 eval；参数是 JSON，本身就是合法的 JavaScript 字面量
        windows[0].run_js(f"window.boxcode.receive({json.dumps({'kind': kind, **data})})")

    def pick_folder() -> str | None:
        paths = windows[0].create_file_dialog(webview.FileDialog.FOLDER)
        return paths[0] if paths else None

    api = GuiApi(Settings(), tasks_dir, results_dir, push, pick_folder)
    window = webview.create_window(
        "BoxCode", html=page_html(), js_api=api, width=1280, height=840, min_size=(1000, 640), text_select=True,
    )
    if window is None:
        raise RuntimeError("pywebview 没能创建窗口")
    windows.append(window)
    try:
        webview.start(debug=debug)
    finally:
        api.shutdown()
