"""文件区：从本地选择文件上传，浏览社区已上传的全部文件。"""

from __future__ import annotations

import streamlit as st

from core import config
from core import files as file_store
from ui import components as c
from views import goto


def render() -> None:
    user = st.session_state.get("user")

    c.hero("SHARED FILES", "文件区",
           f"从本地选择文件上传 · 浏览共享资料　|　"
           f"已收录 {file_store.count_files()} 个文件 / "
           f"{file_store.human_size(file_store.total_size())}")

    # ---------------- 上传 ----------------
    if not user:
        st.warning("请先登录后再上传文件。浏览与下载不受限制。")
        if st.button("去登录 / 注册 →", key="files_goto_login", type="primary"):
            goto("account")
    else:
        with st.form("upload_form", clear_on_submit=True):
            uploads = st.file_uploader(
                "选择本地文件（可多选）",
                accept_multiple_files=True,
                help=f"支持文档 / 图片 / 代码 / 压缩包等，单文件上限 {config.MAX_UPLOAD_MB} MB",
            )
            note = st.text_input("文件说明（可选，≤80 字）", max_chars=80,
                                 placeholder="例如：Transformer 论文精读笔记")
            submitted = st.form_submit_button("⬆ 上传", use_container_width=True)
            if submitted:
                if not uploads:
                    st.error("请先选择要上传的文件")
                else:
                    ok_count, errors = 0, []
                    for f in uploads:
                        ok, msg = file_store.save_upload(
                            user, f.name, bytes(f.getbuffer()), note
                        )
                        if ok:
                            ok_count += 1
                        else:
                            errors.append(f"{f.name}：{msg}")
                    if ok_count:
                        st.success(f"成功上传 {ok_count} 个文件")
                    for err in errors:
                        st.error(err)
                    if ok_count:
                        st.rerun()

    st.divider()

    # ---------------- 浏览 ----------------
    top1, top2 = st.columns([2, 1])
    with top1:
        keyword = st.text_input("搜索文件名 / 上传者", placeholder="输入关键词过滤…")
    with top2:
        only_mine = st.checkbox("只看我上传的", disabled=not user)

    kw = (keyword or "").strip().lower()
    all_files = file_store.list_files(limit=200, username=user if only_mine and user else None)
    if kw:
        all_files = [
            f for f in all_files
            if kw in f["filename"].lower() or kw in f["username"].lower()
        ]

    st.caption(f"共 {len(all_files)} 个文件")

    if not all_files:
        c.empty("📁", "暂无匹配的文件。登录后即可上传第一个资料。")
        return

    for f in all_files:
        with st.container(border=True):
            left, mid, right = st.columns([1.6, 1.1, 3])
            with left:
                st.markdown(
                    f'<div class="g-name">{c.e(f["filename"])}</div>'
                    f'<div class="g-sub">{c.e(f["username"])} · '
                    f'{c.e(f["created_at"])} · {c.e(f["size_human"])}</div>',
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
                    st.caption(f"说明：{f['note']}")
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
