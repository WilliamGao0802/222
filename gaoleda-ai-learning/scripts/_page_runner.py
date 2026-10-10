"""冒烟测试用的单页入口：通过环境变量选择要渲染的页面与登录态。

仅供 scripts/smoke_test.py 使用（AppTest 需要一个真实脚本文件）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from views import account, admin, forum, home, news  # noqa: E402
from views import files as files_view  # noqa: E402

PAGES = {
    "首页": home.render,
    "AI 新闻": news.render,
    "讨论区": forum.render,
    "文件区": files_view.render,
    "我的账户": account.render,
    "管理后台": admin.render,
}

label = os.environ.get("SMOKE_PAGE", "首页")
user = os.environ.get("SMOKE_USER") or None

# 只在会话状态尚未建立时写入，避免覆盖用户在页面内登录/退出的结果
if "user" not in st.session_state:
    st.session_state["user"] = user
if "news_detail" not in st.session_state:
    st.session_state["news_detail"] = os.environ.get("SMOKE_NEWS_DETAIL") or None

PAGES[label]()
