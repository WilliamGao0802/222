"""账户页：未登录时是登录 / 注册；已登录时是个人中心。"""

from __future__ import annotations

import streamlit as st

from core import auth, config, discussion
from core import files as file_store
from ui import components as c
from views import goto, logout, sign_in


def render() -> None:
    user = st.session_state.get("user")
    if user:
        _render_profile(user)
    else:
        _render_auth()


# ------------------------------------------------------------------ 登录 / 注册
def _render_auth() -> None:
    c.hero("ACCOUNT", "登录 / 注册",
           f"仅需用户名与密码 · 密码必须为 {config.PASSWORD_LEN} 位阿拉伯数字")

    quota = auth.remaining_slots()
    st.markdown(
        f'<div class="g-card" style="padding:12px 16px">'
        f'{c.chip(f"已注册 {auth.user_count()} / {config.MAX_USERS}", "cyan")}'
        f'{c.chip(f"剩余名额 {quota}", "mint" if quota > 0 else "amber")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            u = st.text_input("用户名", placeholder="请输入用户名", max_chars=config.USERNAME_MAX)
            p = st.text_input(
                f"密码（{config.PASSWORD_LEN} 位数字）", type="password",
                max_chars=config.PASSWORD_LEN, placeholder="例如 123456",
            )
            if st.form_submit_button("登录", use_container_width=True, type="primary"):
                ok, msg = auth.login(u, p)
                if ok:
                    sign_in(u)
                    st.success(msg + "　登录状态已保存在本机，刷新页面无需重复登录。")
                    st.rerun()
                else:
                    st.error(msg)

    with tab_register:
        if quota <= 0:
            st.error(f"注册用户已达上限（{config.MAX_USERS} 人），暂时无法注册新账号。")
        with st.form("register_form", clear_on_submit=False):
            u2 = st.text_input("用户名", placeholder="2–20 个字符，不含空格", max_chars=config.USERNAME_MAX)
            p2 = st.text_input(
                f"密码（{config.PASSWORD_LEN} 位数字）", type="password",
                max_chars=config.PASSWORD_LEN, placeholder="例如 123456",
            )
            p3 = st.text_input(
                "确认密码", type="password", max_chars=config.PASSWORD_LEN,
                placeholder="请再次输入相同密码",
            )
            if st.form_submit_button("注册", use_container_width=True, type="primary"):
                ok_u, msg_u = auth.validate_username(u2)
                ok_p, msg_p = auth.validate_password(p2)
                if not ok_u:
                    st.error(msg_u)
                elif not ok_p:
                    st.error(msg_p)
                elif p2 != p3:
                    st.error("两次输入的密码不一致，请重新确认")
                else:
                    ok, msg = auth.register(u2, p2)
                    if ok:
                        st.success(msg + "　可直接在上方「登录」标签页登录。")
                    else:
                        st.error(msg)

    st.info(
        "账号说明：本平台仅保存用户名与密码哈希（PBKDF2-HMAC-SHA256 + 随机盐），"
        "不收集邮箱、手机号等任何个人信息。"
    )
    c.footer(
        f"忘记密码？本站不提供找回功能，请牢记你的 {config.PASSWORD_LEN} 位数字密码。"
    )


# ------------------------------------------------------------------ 个人中心
def _render_profile(user: str) -> None:
    info = auth.get_user(user) or {}
    my_posts = discussion.posts_by(user)
    likes_got = sum(p["like_count"] for p in my_posts)
    following = discussion.following_of(user)
    followers = discussion.followers_of(user)
    my_files = file_store.files_by(user)

    c.hero("PROFILE", f"你好，{user}", info.get("bio") or "欢迎回到高乐达的AI学习")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("我的发言", len(my_posts))
    m2.metric("获得点赞", likes_got)
    m3.metric("关注", len(following))
    m4.metric("粉丝", len(followers))

    st.caption(
        f"注册时间：{info.get('created_at', '-')}　|　"
        f"上次登录：{info.get('last_login') or '本次为首次登录'}"
    )

    st.write("")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("💬 去讨论区发言", use_container_width=True):
            goto("forum")
    with b2:
        if st.button("🚪 退出登录", use_container_width=True):
            logout()
            st.success("已退出登录")
            st.rerun()

    st.divider()
    tab1, tab2, tab3 = st.tabs(["个人设置", "我的发言", "我的文件"])

    with tab1:
        with st.form("bio_form"):
            bio = st.text_input("个人简介", value=info.get("bio") or "",
                                max_chars=80, placeholder="一句话介绍自己")
            if st.form_submit_button("保存简介", use_container_width=True):
                ok, msg = auth.set_bio(user, bio)
                st.success(msg) if ok else st.error(msg)
                st.rerun()

        st.write("")
        with st.form("pwd_form", clear_on_submit=True):
            st.caption(f"修改密码（新密码同样必须是 {config.PASSWORD_LEN} 位数字）")
            old = st.text_input("原密码", type="password", max_chars=config.PASSWORD_LEN)
            new = st.text_input("新密码", type="password", max_chars=config.PASSWORD_LEN)
            new2 = st.text_input("确认新密码", type="password", max_chars=config.PASSWORD_LEN)
            if st.form_submit_button("更新密码", use_container_width=True):
                if new != new2:
                    st.error("两次输入的新密码不一致")
                else:
                    ok, msg = auth.change_password(user, old, new)
                    st.success(msg) if ok else st.error(msg)

    with tab2:
        if not my_posts:
            c.empty("✍️", "你还没有发表过发言。")
        for p in my_posts:
            c.list_item(
                f"#{p['id']} · {p['topic']}",
                p["content"][:42] + ("…" if len(p["content"]) > 42 else ""),
                f"❤️ {p['like_count']}　{p['created_at']}",
            )

    with tab3:
        if not my_files:
            c.empty("📁", "你还没有上传过文件。")
        for f in my_files:
            c.list_item(f["filename"], f"{f['created_at']} · {f['size_human']}",
                        f.get("note", ""))

    c.footer(f"账号 ID：{user}　·　{config.APP_NAME} v{config.VERSION}")
