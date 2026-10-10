"""浏览器 Cookie 桥。

读：直接用 Streamlit 原生的 `st.context.cookies`（服务端从请求头解析，无需 JS）。
写：Streamlit 没有内置写 Cookie 的 API，因此用 components.html 注入一小段脚本。
    组件 iframe 继承父页面源，`document.cookie` 会落到应用自身的域上，
    这样下次请求（含刷新页面）浏览器就会带上它。

为什么读和写要分开
    Streamlit 组件无法把值回传给 Python，所以「写」走 JS、「读」走请求头。
    写入后当前这一次脚本运行看不到新 Cookie —— 这没问题：
    登录态已同时写入 st.session_state，Cookie 从下一次页面加载开始生效，
    正好实现「刷新不用重新登录」。
"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components


def read(name: str) -> str:
    """读取 Cookie；取不到时返回空串（不抛异常）。"""
    try:
        jar = st.context.cookies or {}
    except Exception:  # noqa: BLE001  无请求上下文（离线测试等）
        return ""
    try:
        return str(jar.get(name, "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _run_js(js: str) -> None:
    components.html(f"<script>{js}</script>", height=0, width=0)


def _cookie_stmt(name: str, value: str, max_age: int) -> str:
    """返回一段同时作用于当前文档与父文档的写 Cookie 语句。"""
    payload = json.dumps(value)
    stmt = (
        f'"{name}=" + encodeURIComponent({payload}) + '
        f'"; path=/; max-age={int(max_age)}; SameSite=Lax"'
    )
    return f"""
    (function () {{
      var c = {stmt};
      try {{ document.cookie = c; }} catch (e) {{}}
      try {{ if (window.parent && window.parent.document) window.parent.document.cookie = c; }} catch (e) {{}}
    }})();
    """


def set_cookie(name: str, value: str, max_age: int) -> None:
    """写入（或续期）一个 Cookie。"""
    _run_js(_cookie_stmt(name, value, max_age))


def clear_cookie(name: str) -> None:
    """立即过期，等效于删除。"""
    _run_js(_cookie_stmt(name, "", 0))
