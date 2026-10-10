"""首页：品牌主视觉 + 平台数据 + 新闻速览 + 功能入口 + 活跃用户榜。"""

from __future__ import annotations

import streamlit as st

from core import auth, config, discussion
from core import files as file_store
from core import news as news_store
from ui import components as c
from views import goto


def render() -> None:
    user = st.session_state.get("user")

    c.hero(
        "GAOLEDA · AI LEARNING",
        config.APP_NAME,
        config.APP_SLOGAN,
    )

    # ---------------- 平台数据 ----------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("注册用户", f"{auth.user_count()} / {config.MAX_USERS}")
    col2.metric("讨论帖", f"{discussion.count_posts()}")
    col3.metric("共享文件", f"{file_store.count_files()}")
    col4.metric("新闻信源", f"{len(news_store.FEEDS)}")

    st.write("")
    st.subheader("最新 AI 新闻速览")
    news = news_store.fetch_news(3)
    for idx, item in enumerate(news["items"], 1):
        c.card(
            item["title"],
            f'{c.chip(item.get("source", "AI 资讯"), "cyan")}'
            f'{c.chip("🕒 " + item.get("published", ""), "mint")}',
            item.get("summary", ""),
            index=idx,
            link=item.get("link") or None,
        )

    if st.button("查看全部 5 条 AI 新闻 →", key="home_more_news"):
        goto("news")

    # ---------------- 功能入口 ----------------
    st.write("")
    st.subheader("功能入口")
    f1, f2, f3 = st.columns(3)
    with f1:
        c.card("📰 AI 新闻", c.chip("实时更新", "cyan"),
               "聚合多家国际权威信源，展示近一年最具影响力的五条 AI 新闻。")
        if st.button("进入新闻", key="home_goto_news", use_container_width=True):
            goto("news")
    with f2:
        c.card("💬 讨论区", c.chip("互赞 · 互关", "mint"),
               "只对注册用户开放。发表观点、为他人点赞、关注感兴趣的同伴。")
        if st.button("进入讨论区", key="home_goto_forum", use_container_width=True):
            goto("forum")
    with f3:
        c.card("📁 文件区", c.chip("上传 · 浏览", "amber"),
               "从本地选择文件上传共享，随时浏览社区已上传的全部资料。")
        if st.button("进入文件区", key="home_goto_files", use_container_width=True):
            goto("files")

    if not user:
        st.info("当前未登录。注册 / 登录后即可发言、点赞、关注和上传文件。")
        if st.button("立即注册 / 登录 →", key="home_goto_account", type="primary"):
            goto("account")

    # ---------------- 活跃用户榜 ----------------
    st.write("")
    st.subheader("活跃用户榜")
    board = [u for u in discussion.active_users(8) if u.get("posts") or u.get("likes")]
    if not board:
        c.empty("🌱", "还没有人开始发言，成为第一个吧。")
    else:
        for rank, row in enumerate(board, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
            c.list_item(
                f"{medal} {row['username']}",
                f"发帖 {row['posts']} · 获赞 {row['likes']}",
                avatar=row["username"],
            )

    c.footer(
        f"{config.APP_NAME} · v{config.VERSION}　|　"
        "本站为学习交流社区，新闻内容来自公开信源，版权归原作者所有。<br>"
        "Powered by Streamlit · 单文件 SQLite 持久化"
    )
