"""讨论区：仅注册用户可发言；支持互相点赞、互相关注。"""

from __future__ import annotations

import streamlit as st

from core import auth, config, discussion
from ui import components as c
from views import goto


def _header_html(post: dict) -> str:
    initial = c.e((post["username"] or "?")[0].upper())
    topic = post.get("topic") or "综合"
    return (
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">'
        f'<div style="width:34px;height:34px;border-radius:50%;flex:0 0 34px;'
        f'display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;'
        f'background:linear-gradient(135deg,#7C6CF6,#22D3EE)">{initial}</div>'
        f"<div>"
        f'<div style="font-weight:700;color:#fff;font-size:14.5px">{c.e(post["username"])}</div>'
        f'<div style="color:#6E7799;font-size:12px">{c.e(post["created_at"])}'
        f'　{c.chip(topic, "cyan")}</div>'
        f"</div></div>"
    )


def render() -> None:
    user = st.session_state.get("user")

    c.hero("DISCUSSION", "讨论区",
           f"仅注册用户可发言 · 互相点赞 · 互相关注　|　"
           f"现有 {discussion.count_posts()} 条发言")

    # ---------------- 发言框 ----------------
    if not user:
        st.warning("请先登录后再参与讨论。")
        if st.button("去登录 / 注册 →", key="forum_goto_login", type="primary"):
            goto("account")
    else:
        with st.form("post_form", clear_on_submit=True):
            content = st.text_area(
                "发表你的看法",
                max_chars=config.MAX_POST_LEN,
                placeholder="分享你对 AI 的观察、疑问或学习心得…（最多 500 字）",
                height=110,
            )
            left, right = st.columns([2, 1])
            with left:
                topic = st.selectbox("话题分类", discussion.TOPICS, index=0)
            with right:
                st.write("")
                st.write("")
                submitted = st.form_submit_button("发布", use_container_width=True)
            if submitted:
                ok, msg = discussion.add_post(user, content, topic)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

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
                    c.list_item(name, f"发帖 {len(discussion.posts_by(name))}")
            else:
                st.caption("还没有关注任何人。")
        with g2:
            st.caption(f"关注我的人（{len(followers)}）")
            if followers:
                for name in followers[:20]:
                    c.list_item(name, "已关注你")
            else:
                st.caption("暂时还没有粉丝。")

    c.footer("发言请遵守社区礼仪，勿发布违法、侵权或攻击性内容。")
