"""讨论区：仅注册用户可发言；支持互相点赞、互相关注；带草稿箱。

草稿箱的状态刷新时序（容易踩坑，单独说明）
- Streamlit 不允许在「控件已创建之后」改写它的 session_state。
- 因此「载入草稿 / 清空输入」这类要改写输入框内容的操作，不在点击当次生效，
  而是只记一个待处理标记，然后 rerun；下一轮在**创建控件之前**统一消费掉。
"""

from __future__ import annotations

import streamlit as st

from core import config, discussion, drafts
from ui import components as c
from views import goto


def _header_html(post: dict) -> str:
    topic = post.get("topic") or "综合"
    return (
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
        f"{c.avatar_block(post['username'], 34)}"
        f"<div>"
        f'<div style="font-weight:700;color:#fff;font-size:14.5px">'
        f'{c.e(post["username"])}</div>'
        f'<div style="color:#6E7799;font-size:12px">{c.e(post["created_at"])}'
        f'　{c.chip(topic, "cyan")}</div>'
        f"</div></div>"
    )


def _consume_pending_edits(user: str | None) -> None:
    """在创建任何输入控件之前，消费「载入草稿 / 清空输入」请求。"""
    st.session_state.setdefault("post_content", "")
    st.session_state.setdefault("post_topic", discussion.TOPICS[0])
    st.session_state.setdefault("editing_draft", None)

    pending_load = st.session_state.pop("_load_draft", None)
    if pending_load is not None and user:
        draft = drafts.get_draft(int(pending_load), user)
        if draft:
            st.session_state["post_content"] = draft["content"]
            st.session_state["post_topic"] = (
                draft["topic"] if draft["topic"] in discussion.TOPICS
                else discussion.TOPICS[0]
            )
            st.session_state["editing_draft"] = draft["id"]
            st.session_state["_draft_notice"] = (
                f"已载入草稿 #{draft['id']}，改完可直接发布或再次存入草稿箱。"
            )

    if st.session_state.pop("_reset_content", False):
        st.session_state["post_content"] = ""
        st.session_state["post_topic"] = discussion.TOPICS[0]
        st.session_state["editing_draft"] = None


def _render_draft_box(user: str) -> None:
    my_drafts = drafts.list_drafts(user)
    with st.expander(f"📝 我的草稿箱（{len(my_drafts)} 条）", expanded=False):
        if not my_drafts:
            st.caption("草稿箱是空的。写发言时点「📝 存入草稿箱」即可保存，随时回来继续写。")
            return

        for d in my_drafts:
            preview = d["content"][:160] + ("…" if len(d["content"]) > 160 else "")
            with st.container(border=True):
                st.markdown(
                    f'<div class="g-sub">草稿 #{d["id"]} · {c.e(d["topic"])} · '
                    f'更新于 {c.e(d["updated_at"])}</div>'
                    f'<div style="color:#D6DAF0;font-size:14px;line-height:1.85;margin:7px 0 4px">'
                    f'{c.e(preview)}</div>',
                    unsafe_allow_html=True,
                )
                k1, k2, k3 = st.columns(3)
                with k1:
                    if st.button("↧ 载入编辑器", key=f"loadd_{d['id']}",
                                 use_container_width=True):
                        st.session_state["_load_draft"] = d["id"]
                        st.rerun()
                with k2:
                    if st.button("🚀 直接发布", key=f"pubd_{d['id']}",
                                 use_container_width=True):
                        ok, msg = discussion.add_post(user, d["content"], d["topic"])
                        if ok:
                            drafts.delete_draft(d["id"], user)
                            st.session_state["_draft_notice"] = "草稿已发布到讨论区。"
                        else:
                            st.error(msg)
                        st.rerun()
                with k3:
                    if st.button("🗑 删除草稿", key=f"deld_{d['id']}",
                                 use_container_width=True):
                        ok, msg = drafts.delete_draft(d["id"], user)
                        st.session_state["_draft_notice"] = msg
                        st.rerun()


def render() -> None:
    user = st.session_state.get("user")
    _consume_pending_edits(user)

    c.hero("DISCUSSION", "讨论区",
           f"仅注册用户可发言 · 互相点赞 · 互相关注 · 草稿箱　|　"
           f"现有 {discussion.count_posts()} 条发言")

    notice = st.session_state.pop("_draft_notice", "")
    if notice:
        st.success(notice)

    # ---------------- 发言框 ----------------
    if not user:
        st.warning("请先登录后再参与讨论。")
        if st.button("去登录 / 注册 →", key="forum_goto_login", type="primary"):
            goto("account")
    else:
        editing_id = st.session_state.get("editing_draft")
        if editing_id:
            st.info(f"正在编辑草稿 #{editing_id} —— 发布后该草稿会自动从草稿箱移除。"
                    f"想放弃编辑可点「🗑 清空输入」。")

        with st.form("post_form", clear_on_submit=False):
            st.text_area(
                "发表你的看法",
                key="post_content",
                max_chars=config.MAX_POST_LEN,
                placeholder="分享你对 AI 的观察、疑问或学习心得…（最多 500 字）",
                height=110,
            )
            left, right = st.columns([2, 1])
            with left:
                st.selectbox("话题分类", discussion.TOPICS, key="post_topic")
                if st.form_submit_button("🗑 清空输入", use_container_width=True):
                    st.session_state["_reset_content"] = True
                    st.rerun()
            with right:
                if st.form_submit_button("发布", use_container_width=True, type="primary"):
                    ok, msg = discussion.add_post(
                        user,
                        st.session_state["post_content"],
                        st.session_state["post_topic"],
                    )
                    if ok:
                        if st.session_state.get("editing_draft"):
                            drafts.delete_draft(st.session_state["editing_draft"], user)
                        st.session_state["_reset_content"] = True
                        st.session_state["_draft_notice"] = msg
                        st.rerun()
                    else:
                        st.error(msg)
                if st.form_submit_button("📝 存入草稿箱", use_container_width=True):
                    ok, msg, draft_id = drafts.save_draft(
                        user,
                        st.session_state["post_content"],
                        st.session_state["post_topic"],
                        st.session_state.get("editing_draft"),
                    )
                    if ok:
                        st.session_state["editing_draft"] = draft_id
                        st.session_state["_draft_notice"] = msg
                        st.rerun()
                    else:
                        st.error(msg)

        st.write("")
        _render_draft_box(user)

    st.divider()

    # ---------------- 筛选 ----------------
    f1, f2, f3 = st.columns([1.4, 1.4, 1.2])
    with f1:
        topic_filter = st.selectbox(
            "话题筛选", ["全部"] + discussion.TOPICS, index=0, key="forum_topic"
        )
    with f2:
        only_following = st.checkbox("只看我关注的人", key="forum_only_following",
                                     disabled=not user)
    with f3:
        st.write("")
        st.caption(f"共 {discussion.count_posts()} 条")

    posts = discussion.list_posts(
        limit=80,
        viewer=user,
        topic=topic_filter,
        only_following=only_following and bool(user),
    )

    if not posts:
        c.empty("💬", "这里还很安静，来发布第一条发言吧。")
        return

    for post in posts:
        with st.container(border=True):
            st.markdown(_header_html(post), unsafe_allow_html=True)
            st.markdown(
                f'<p style="color:#D6DAF0;font-size:15px;line-height:1.95;margin:2px 0 10px">'
                f'{c.e(post["content"])}</p>',
                unsafe_allow_html=True,
            )

            b1, b2, b3, b4 = st.columns([1.1, 1.1, 1.1, 3])
            liked = post["liked_by_me"]
            with b1:
                if st.button(
                    f"{'❤️' if liked else '🤍'} {post['like_count']}",
                    key=f"like_{post['id']}",
                    use_container_width=True,
                ):
                    if not user:
                        st.warning("请先登录后再点赞")
                    else:
                        ok, msg, _ = discussion.toggle_like(post["id"], user)
                        st.toast(msg) if ok else st.error(msg)
                        st.rerun()

            with b2:
                if user and post["username"] != user:
                    following = post["followed_by_me"]
                    if st.button(
                        "已关注" if following else "＋关注",
                        key=f"follow_{post['id']}",
                        use_container_width=True,
                    ):
                        ok, msg, _ = discussion.toggle_follow(user, post["username"])
                        st.toast(msg) if ok else st.error(msg)
                        st.rerun()
                elif not user:
                    if st.button("＋关注", key=f"follow_anon_{post['id']}",
                                 use_container_width=True):
                        st.warning("请先登录后再关注")

            with b3:
                if user and post["username"] == user:
                    if st.button("🗑 删除", key=f"del_{post['id']}",
                                 use_container_width=True):
                        ok, msg = discussion.delete_post(post["id"], user)
                        st.toast(msg) if ok else st.error(msg)
                        st.rerun()

            with b4:
                likers = discussion.who_liked(post["id"])
                if likers:
                    preview = "、".join(likers[:4]) + ("…" if len(likers) > 4 else "")
                    st.caption(f"❤️ {len(likers)} 人点赞：{preview}")

    # ---------------- 我的关注 ----------------
    if user:
        st.divider()
        following = discussion.following_of(user)
        followers = discussion.followers_of(user)
        st.subheader("我的社交关系")
        g1, g2 = st.columns(2)
        with g1:
            st.caption(f"我关注的人（{len(following)}）")
            if following:
                for name in following[:20]:
                    c.list_item(name, f"发帖 {len(discussion.posts_by(name))}", avatar=name)
            else:
                st.caption("还没有关注任何人。")
        with g2:
            st.caption(f"关注我的人（{len(followers)}）")
            if followers:
                for name in followers[:20]:
                    c.list_item(name, "已关注你", avatar=name)
            else:
                st.caption("暂时还没有粉丝。")

    c.footer("发言请遵守社区礼仪，勿发布违法、侵权或攻击性内容。")
