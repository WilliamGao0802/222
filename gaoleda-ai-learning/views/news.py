"""AI 新闻页：列表 → 详情 两级视图，支持手动刷新与跳转原文。"""

from __future__ import annotations

import streamlit as st

from core import config
from core import news as news_store
from ui import components as c
from views import goto


def _ensure_state() -> None:
    st.session_state.setdefault("news_detail", None)


def _load(force: bool = False) -> dict:
    return news_store.fetch_news(config.NEWS_LIMIT, force=force)


def render() -> None:
    _ensure_state()

    detail_title = st.session_state.get("news_detail")
    if detail_title:
        _render_detail(detail_title)
    else:
        _render_list()


# ------------------------------------------------------------------ 列表
def _render_list() -> None:
    c.hero("AI NEWSROOM", "AI 前沿新闻",
           "近一年最具影响力的五条 AI 新闻 · 每 30 分钟自动刷新")

    top_left, top_right = st.columns([3, 1])
    with top_right:
        refresh = st.button("🔄 刷新新闻", use_container_width=True)

    with st.spinner("正在聚合最新信源…"):
        data = _load(force=refresh)

    status = (
        f'{c.chip("实时信源", "mint")}' if data["live"]
        else f'{c.chip("精选归档", "amber")}'
    )
    st.markdown(
        f'<div class="g-card" style="padding:12px 16px">'
        f'{status} {c.chip("更新于 " + data.get("updated_at", "-"), "cyan")}'
        f'<span style="color:#9BA3C7;font-size:13px;margin-left:10px">{c.e(data.get("note", ""))}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    for idx, item in enumerate(data["items"], 1):
        c.card(
            item["title"],
            f'{c.chip(item.get("source", "AI 资讯"), "cyan")}'
            f'{c.chip("🕒 " + item.get("published", ""), "mint")}'
            + (f'{c.chip("精选", "amber")}' if item.get("fallback") else ""),
            item.get("summary", ""),
            index=idx,
        )
        b1, b2, _ = st.columns([1.2, 1.2, 3])
        with b1:
            if st.button("📖 查看详情", key=f"news_detail_{idx}", use_container_width=True):
                st.session_state["news_detail"] = item["title"]
                st.rerun()
        with b2:
            if item.get("link"):
                st.link_button("🔗 阅读原文", item["link"], use_container_width=True)
        st.write("")

    c.footer(
        "新闻内容自动抓取自公开 RSS 信源，版权归原作者所有；"
        "标有「精选」的条目为归档内容，用于信源不可达时保证页面完整。"
    )


# ------------------------------------------------------------------ 详情
def _render_detail(title: str) -> None:
    item = news_store.get_news_by_title(title)

    if st.button("← 返回新闻列表", key="news_back"):
        st.session_state["news_detail"] = None
        st.rerun()

    if not item:
        c.empty("🕳️", "该新闻已不在当前列表中，可能已被新内容替换。")
        return

    c.hero(
        item.get("source", "AI NEWS"),
        item["title"],
        f'发布于 {item.get("published", "未知时间")} · 来源：{item.get("source", "公开信源")}',
    )

    st.markdown(
        f'<div class="g-card">'
        f'<div class="g-meta">'
        f'{c.chip(item.get("source", "AI 资讯"), "cyan")}'
        f'{c.chip("🕒 " + item.get("published", ""), "mint")}'
        + (f'{c.chip("精选归档", "amber")}' if item.get("fallback") else "")
        + f"</div>"
        f'<p class="g-body" style="font-size:15.5px;line-height:2">'
        f'{c.e(item.get("summary", ""))}</p></div>',
        unsafe_allow_html=True,
    )

    st.write("")
    st.subheader("延伸阅读")
    if item.get("link"):
        st.link_button("🔗 打开原文链接（外部站点）", item["link"], use_container_width=True)
    else:
        st.caption("该条目未提供外部链接。")

    st.caption(
        "提示：外部链接会在新标签页打开，内容与本站无关，请自行判断其可靠性。"
    )

    st.write("")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("← 返回列表", key="news_back_bottom", use_container_width=True):
            st.session_state["news_detail"] = None
            st.rerun()
    with b2:
        if st.button("🏠 回到首页", key="news_home", use_container_width=True):
            st.session_state["news_detail"] = None
            goto("home")
