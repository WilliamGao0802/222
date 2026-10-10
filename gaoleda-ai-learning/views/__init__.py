"""页面视图包：每个模块导出一个 render()，由 app.py 用 st.navigation 挂载。"""

from __future__ import annotations

import streamlit as st


def goto(key: str) -> None:
    """在应用内跳转到指定页面（st.navigation 页面对象）。"""
    page = st.session_state.get("_pages", {}).get(key)
    if page is None:
        st.rerun()
        return
    try:
        st.switch_page(page)
    except Exception:
        st.rerun()
