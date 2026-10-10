"""页面视图包：每个模块导出一个 render()，由 app.py 用 st.navigation 挂载。"""

from __future__ import annotations

import streamlit as st

from core import config, session as session_store
from ui import browser


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


# ------------------------------------------------------------------ 登录态
def sign_in(username: str) -> None:
    """登录成功后统一处理：写内存状态 + 写浏览器 Cookie（记住登录）。"""
    name = (username or "").strip()
    st.session_state["user"] = name
    st.session_state["news_detail"] = None
    token = session_store.issue(name)
    if token:
        browser.set_cookie(config.SESSION_COOKIE, token, session_store.max_age())


def logout() -> None:
    """退出登录：清内存状态 + 清浏览器 Cookie。"""
    st.session_state["user"] = None
    st.session_state["news_detail"] = None
    browser.clear_cookie(config.SESSION_COOKIE)


def restore_session() -> bool:
    """用浏览器 Cookie 恢复登录态（刷新页面不掉线）。返回是否恢复了会话。"""
    if st.session_state.get("user"):
        return False
    token = browser.read(config.SESSION_COOKIE)
    if not token:
        return False
    name = session_store.verify(token)
    if not name:
        browser.clear_cookie(config.SESSION_COOKIE)   # 令牌已失效，顺手清掉
        return False
    from core import auth

    if not auth.user_exists(name):
        browser.clear_cookie(config.SESSION_COOKIE)
        return False
    st.session_state["user"] = name
    st.session_state["session_restored"] = True
    return True
