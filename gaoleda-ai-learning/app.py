"""高乐达的AI学习 —— 应用入口（只负责页面路由与全局侧边栏）。

架构
    app.py          路由 + 全局壳层
    views/*.py      各页面的渲染函数（只调 core，不直接读写数据库）
    core/*.py       纯 Python 业务逻辑（不 import streamlit，可离线单测）
    ui/*.py         主题与可复用组件

启动
    streamlit run app.py
"""

from __future__ import annotations


def _should_bootstrap() -> bool:
    """判断当前是否是被 `python app.py` 直接拉起（而非 `streamlit run`）。

    三个信号任一命中就说明已经处于 Streamlit 运行时中，不再二次启动：
      1. 引导标记已写入环境变量（本进程内 set 后由嵌套调用继承）；
      2. 命令行里出现 streamlit（`streamlit run app.py`）；
      3. 当前进程内已存在 Streamlit Runtime 实例。
    """
    import os
    import sys

    if os.environ.get("GAOLEDA_BOOTSTRAPPED") == "1":
        return False
    if "streamlit" in " ".join(sys.argv[:3]).lower():
        return False
    try:
        from streamlit.runtime import exists as _runtime_exists

        if _runtime_exists():
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


def _launch_standalone() -> None:
    """把本文件作为 Streamlit 应用启动。

    很多托管平台只给一条启动命令、且不保证经过 shell 展开环境变量，
    因此这里直接读 os.environ["PORT"]，比 `--server.port=$PORT` 更稳。
    """
    import os
    import sys

    os.environ["GAOLEDA_BOOTSTRAPPED"] = "1"

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit", "run", os.path.abspath(__file__),
        "--server.port", str(os.environ.get("PORT", "8501")),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--server.fileWatcherType", "none",
        "--browser.gatherUsageStats", "false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__" and _should_bootstrap():
    _launch_standalone()


# ================================================================ 应用本体
import streamlit as st  # noqa: E402

from core import auth, config, discussion  # noqa: E402
from core import admin as admin_core  # noqa: E402
from core import files as file_store  # noqa: E402
from ui import components as c  # noqa: E402
from ui import theme  # noqa: E402
from views import account, admin, forum, home, news  # noqa: E402
from views import files as files_view  # noqa: E402
from views import logout, restore_session  # noqa: E402

# ---------------------------------------------------------------- 页面配置
st.set_page_config(
    page_title=config.APP_NAME,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="auto",  # 桌面展开、移动端收起
    menu_items={
        "About": f"{config.APP_NAME} v{config.VERSION}\n\n{config.APP_SLOGAN}\n\n"
                 "探索人工智能前沿 · 交流 · 成长",
    },
)

theme.inject()

st.session_state.setdefault("user", None)
st.session_state.setdefault("news_detail", None)

# 用浏览器 Cookie 恢复登录态 —— 刷新页面不需要重新登录
restore_session()

# 每次会话同步一次管理员角色（把名单内的老账号补成管理员）
if not st.session_state.get("_admin_synced"):
    admin_core.sync_admin_roles()
    st.session_state["_admin_synced"] = True

# ---------------------------------------------------------------- 页面注册
page_home = st.Page(home.render, title="首页", icon="🏠", url_path="home", default=True)
page_news = st.Page(news.render, title="AI 新闻", icon="📰", url_path="news")
page_forum = st.Page(forum.render, title="讨论区", icon="💬", url_path="forum")
page_files = st.Page(files_view.render, title="文件区", icon="📁", url_path="files")
page_account = st.Page(account.render, title="我的账户", icon="👤", url_path="account")
page_admin = st.Page(admin.render, title="管理后台", icon="🛡️", url_path="admin")

st.session_state["_pages"] = {
    "home": page_home,
    "news": page_news,
    "forum": page_forum,
    "files": page_files,
    "account": page_account,
    "admin": page_admin,
}

_sections = {
    "导览": [page_home, page_news, page_forum, page_files],
    "账户": [page_account],
}
if admin_core.is_admin(st.session_state.get("user")):
    _sections["管理"] = [page_admin]

nav = st.navigation(_sections)

# ---------------------------------------------------------------- 全局侧边栏
with st.sidebar:
    st.markdown(
        f'<div style="padding:2px 2px 12px">'
        f'<div style="font-size:19px;font-weight:800;letter-spacing:.5px;'
        f'background:linear-gradient(100deg,#C7BEFF,#22D3EE);'
        f'-webkit-background-clip:text;background-clip:text;'
        f'-webkit-text-fill-color:transparent">🧠 {config.APP_NAME}</div>'
        f'<div style="color:#6E7799;font-size:11.5px;letter-spacing:2px;margin-top:2px">'
        f"AI LEARNING COMMUNITY</div></div>",
        unsafe_allow_html=True,
    )

    user = st.session_state.get("user")
    if user:
        info = auth.get_user(user) or {}
        c.user_box(user, info.get("bio") or "已登录")
        if st.button("退出登录", use_container_width=True, key="sidebar_logout"):
            logout()
            st.rerun()
    else:
        st.info("当前未登录，仅可浏览公开内容。")
        if st.button("登录 / 注册", use_container_width=True, key="sidebar_login",
                     type="primary"):
            try:
                st.switch_page(page_account)
            except Exception:
                st.rerun()

    st.divider()
    st.caption(
        f"注册用户　{auth.user_count()} / {config.MAX_USERS}\n\n"
        f"讨论帖　　　{discussion.count_posts()}\n\n"
        f"共享文件　　{file_store.count_files()}（"
        f"{file_store.human_size(file_store.total_size())}）"
    )
    st.divider()
    st.caption(f"v{config.VERSION} · 单文件 SQLite 持久化")

# ---------------------------------------------------------------- 运行
nav.run()
