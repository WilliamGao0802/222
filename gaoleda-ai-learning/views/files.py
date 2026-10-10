"""文件区：按仓库分类上传文件，并用站内搜索引擎检索已上传资料。

四个仓库（config.FILE_REPOS）：算法 / 文章 / 语法 / 题解。
搜索引擎支持：多关键词（空格分隔、同时满足）、搜索范围（全部字段 / 文件名 / 说明 / 上传者）、
仓库筛选、排序方式，并对命中关键词做高亮。
"""

from __future__ import annotations

import re

import streamlit as st

from core import config
from core import files as file_store
from ui import components as c
from views import goto

_REPO_CHIP_KINDS = ("cyan", "mint", "amber", "")


def _highlight(text: str, terms: list[str]) -> str:
    """把命中的关键词高亮。先转义再替换，不会引入 XSS。"""
    out = c.e(text)
    for term in terms:
        escaped = c.e(term)
        if not escaped:
            continue
        out = re.sub(
            f"({re.escape(escaped)})",
            r'<mark style="background:rgba(124,108,246,.40);color:#fff;'
            r'border-radius:4px;padding:0 3px;font-weight:600">\1</mark>',
            out,
            flags=re.IGNORECASE,
        )
    return out


def _label_to_key(mapping: dict[str, str], label: str, fallback: str) -> str:
    for key, value in mapping.items():
        if value == label:
            return key
    return fallback


def render() -> None:
    # 清空搜索需要改写输入框，必须在控件创建之前完成
    if st.session_state.pop("_clear_file_kw", False):
        st.session_state["file_kw"] = ""

    user = st.session_state.get("user")
    counts = file_store.repo_counts()

    c.hero("SHARED FILES", "文件区",
           f"按仓库分类上传 · 站内搜索　|　已收录 {file_store.count_files()} 个文件 / "
           f"{file_store.human_size(file_store.total_size())}")

    chips = "".join(
        c.chip(f"{repo}　{counts.get(repo, 0)}", _REPO_CHIP_KINDS[i % 4])
        for i, repo in enumerate(config.FILE_REPOS)
    )
    st.markdown(
        f'<div class="g-card" style="padding:12px 16px">{chips}</div>',
        unsafe_allow_html=True,
    )

    # ---------------- 上传 ----------------
    if not user:
        st.warning("请先登录后再上传文件。浏览、搜索与下载不受限制。")
        if st.button("去登录 / 注册 →", key="files_goto_login", type="primary"):
            goto("account")
    else:
        with st.form("upload_form", clear_on_submit=True):
            repo = st.selectbox(
                "选择仓库", config.FILE_REPOS, index=0,
                help="上传的资料会归入所选仓库，方便其他人按仓库浏览与检索",
            )
            uploads = st.file_uploader(
                f"选择本地文件（可多选，单文件上限 {config.MAX_UPLOAD_MB} MB）",
                accept_multiple_files=True,
            )
            note = st.text_input("文件说明（可选，≤80 字）", max_chars=80,
                                 placeholder="例如：Transformer 论文精读笔记")
            if st.form_submit_button("⬆ 上传到该仓库", use_container_width=True):
                if not uploads:
                    st.error("请先选择要上传的文件")
                else:
                    ok_count, errors = 0, []
                    for f in uploads:
                        ok, msg = file_store.save_upload(
                            user, f.name, bytes(f.getbuffer()), note, repo
                        )
                        if ok:
                            ok_count += 1
                        else:
                            errors.append(f"{f.name}：{msg}")
                    if ok_count:
                        st.success(f"成功上传 {ok_count} 个文件到「{repo}」仓库")
                    for err in errors:
                        st.error(err)
                    if ok_count:
                        st.rerun()

    st.divider()

    # ---------------- 搜索引擎 ----------------
    st.subheader("🔎 站内搜索")
    q1, q2, q3 = st.columns([2.4, 1.25, 1.25])
    with q1:
        keyword = st.text_input(
            "关键词", key="file_kw",
            placeholder="多个关键词用空格分隔，例如：论文 transformer",
            help="多个关键词之间是「同时满足」关系",
        )
    with q2:
        scope_label = st.selectbox(
            "搜索范围", list(file_store.SEARCH_SCOPES.values()), key="file_scope"
        )
    with q3:
        order_label = st.selectbox(
            "排序方式", list(file_store.ORDERINGS.values()), key="file_order"
        )

    r1, r2, r3 = st.columns([2.6, 1, 1])
    with r1:
        repo_filter = st.radio(
            "仓库筛选", [config.ALL_REPOS] + config.FILE_REPOS,
            horizontal=True, key="file_repo",
        )
    with r2:
        st.write("")
        only_mine = st.checkbox("只看我上传的", disabled=not user, key="file_mine")
    with r3:
        st.write("")
        if st.button("清空搜索", use_container_width=True):
            st.session_state["_clear_file_kw"] = True
            st.rerun()

    scope = _label_to_key(file_store.SEARCH_SCOPES, scope_label, "all")
    order = _label_to_key(file_store.ORDERINGS, order_label, "new")
    terms = [t for t in (keyword or "").split() if t]

    results = file_store.search_files(
        keyword=keyword,
        scope=scope,
        repo=None if repo_filter == config.ALL_REPOS else repo_filter,
        order=order,
        limit=200,
        username=user if (only_mine and user) else None,
    )

    st.caption(
        f"检索到 {len(results)} 个文件"
        + (f"　|　关键词：{'、'.join(terms)}" if terms else "")
        + (f"　|　仓库：{repo_filter}" if repo_filter != config.ALL_REPOS else "")
    )

    if not results:
        if terms or repo_filter != config.ALL_REPOS:
            c.empty("🔍", "没有匹配的文件。试试更换关键词、放宽搜索范围，或切到「全部」仓库。")
        else:
            c.empty("📁", "还没有文件。登录后即可上传第一个资料。")
        return

    # ---------------- 结果列表 ----------------
    for f in results:
        with st.container(border=True):
            left, mid, right = st.columns([1.7, 1.05, 2.9])
            with left:
                st.markdown(
                    f'<div class="g-name">{_highlight(f["filename"], terms)}</div>'
                    f'<div class="g-sub">{c.chip(f["repo"], "cyan")}　'
                    f'上传者 {_highlight(f["username"], terms)}　'
                    f'{c.e(f["created_at"])}　{c.e(f["size_human"])}</div>',
                    unsafe_allow_html=True,
                )
            with mid:
                data = file_store.read_file(f["stored_name"])
                if data is not None:
                    st.download_button(
                        "⬇ 下载",
                        data=data,
                        file_name=f["filename"],
                        key=f"dl_{f['id']}",
                        use_container_width=True,
                    )
                else:
                    st.caption("文件已丢失")
            with right:
                if f.get("note"):
                    st.markdown(
                        f'<div class="g-sub">说明：{_highlight(f["note"], terms)}</div>',
                        unsafe_allow_html=True,
                    )
                if user and f["username"] == user:
                    if st.button("🗑 删除", key=f"delf_{f['id']}"):
                        ok, msg = file_store.delete_file(f["id"], user)
                        st.toast(msg) if ok else st.error(msg)
                        st.rerun()
                elif not user:
                    st.caption("登录后可上传与管理自己的文件")

    c.footer(
        "请勿上传含有个人隐私、侵权或违法内容的文件；"
        "上传即表示你拥有该文件的分享权利。"
    )
