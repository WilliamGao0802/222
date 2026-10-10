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
    """登录成功后统一处理：写内存状态 + 排队写浏览器 Cookie（记住登录）。"""
    from core import auth

    name = (username or "").strip()
    st.session_state["user"] = name
    st.session_state["news_detail"] = None
    epoch = auth.session_epoch(name) or 0
    token = session_store.issue(name, epoch)
    if token:
        st.session_state["_cookie_cmd"] = (
            config.SESSION_COOKIE, token, session_store.max_age()
        )


def logout() -> None:
    """退出登录：作废旧令牌 + 清内存状态 + 排队清除浏览器 Cookie。"""
    from core import auth

    user = st.session_state.get("user")
    if user:
        # 服务端确定性作废：世代号 +1，旧令牌立刻失效。
        # 只靠 JS 删 Cookie 不够——它是异步的，而 st.context.cookies 在同一个
        # 会话内读到的是页面首次加载时的快照，会把刚退出的账号又「恢复」回来。
        auth.bump_session_epoch(user)
    st.session_state["user"] = None
    st.session_state["news_detail"] = None
    st.session_state["_cookie_cmd"] = (config.SESSION_COOKIE, "", 0)


def flush_cookie() -> None:
    """把排队中的登录 Cookie 落地（由 app.py 在每轮脚本开头调用）。

    为什么要「排队到下一轮」而不是当场写入：
        登录 / 退出的处理器后面都紧跟 `st.rerun()`，本轮注入的 iframe
        很可能还没来得及被浏览器加载，就被下一轮渲染替换掉了。
        攒到下一轮（不再触发 rerun 的那一轮）再注入才稳定生效。
    """
    cmd = st.session_state.pop("_cookie_cmd", None)
    if not cmd:
        return
    name, value, max_age = cmd
    if value:
        browser.set_cookie(name, value, max_age)
    else:
        browser.clear_cookie(name)


def has_pending_cookie() -> bool:
    """本轮是否有待写入 / 待清除的 Cookie（用于决定要不要恢复登录态）。"""
    return bool(st.session_state.get("_cookie_cmd"))


def restore_session() -> bool:
    """用浏览器 Cookie 恢复登录态（刷新页面不掉线）。返回是否恢复了会话。"""
    if st.session_state.get("user"):
        return False
    token = browser.read(config.SESSION_COOKIE)
    if not token:
        return False
    parsed = session_store.verify(token)
    if not parsed:
        browser.clear_cookie(config.SESSION_COOKIE)   # 令牌已失效，顺手清掉
        return False
    name, epoch = parsed
    from core import auth

    # 世代号必须与库里一致：退出登录后旧令牌在此被拒绝，
    # 因此即便浏览器 Cookie 还没删掉（或 st.context.cookies 读到旧快照），也不会被拉回登录态。
    if not auth.user_exists(name) or auth.session_epoch(name) != epoch:
        browser.clear_cookie(config.SESSION_COOKIE)
        return False
    st.session_state["user"] = name
    st.session_state["session_restored"] = True
    return True
