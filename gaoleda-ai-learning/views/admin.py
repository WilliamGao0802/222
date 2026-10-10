"""管理后台页面：仅管理员可见。

功能
- 成员总览：用户名、角色、手机号、注册时间、上次登录、发帖 / 文件 / 草稿 / 获赞
- 查看密码：默认打码，点「显示明文」后才展开（防肩窥）
- 重置密码：管理员直接把成员密码改成指定值
- 删除账户：需勾选确认，级联清理该成员的全部内容
"""

from __future__ import annotations

import streamlit as st

from core import admin, config
from ui import components as c


def _initial_block(name: str, is_admin: bool, size: int = 40) -> str:
    initial = c.e((name or "?")[0].upper())
    ring = "box-shadow:0 0 0 2px rgba(34,211,238,.55)" if is_admin else "none"
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;flex:0 0 {size}px;'
        f'display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;'
        f'font-size:{max(13, size // 2)}px;{ring};'
        f'background:linear-gradient(135deg,#7C6CF6,#22D3EE)">{initial}</div>'
    )


def render() -> None:
    user = st.session_state.get("user")

    if not user or not admin.is_admin(user):
        c.hero("ADMIN", "无权访问", "该页面仅对管理员开放")
        st.error("当前账号没有管理员权限。请使用管理员账号登录后再访问。")
        if not user:
            st.caption("提示：你还未登录。")
        return

    c.hero(
        "ADMIN CONSOLE",
        "管理后台",
        f"管理员 {user}　|　成员总览 · 密码查看 · 账户删除",
    )

    data = admin.stats()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("成员总数", f"{data['members']} / {config.MAX_USERS}")
    m2.metric("管理员", data["admins"])
    m3.metric("讨论帖", data["posts"])
    m4.metric("共享文件", data["files"])
    m5.metric("草稿", data["drafts"])

    st.divider()

    # ---------------- 检索与显示开关 ----------------
    s1, s2, s3 = st.columns([2.2, 1, 1])
    with s1:
        keyword = st.text_input(
            "检索成员", placeholder="按用户名或手机号过滤…", key="admin_kw"
        )
    with s2:
        st.write("")
        show_pwd = st.checkbox("显示明文密码", key="admin_show_pwd")
    with s3:
        st.write("")
        st.caption("默认打码，避免旁人看到")

    members = admin.list_members(keyword)
    st.caption(f"共 {len(members)} 名成员")

    if not members:
        c.empty("🔍", "没有匹配的成员。")
        return

    # ---------------- 成员列表 ----------------
    for m in members:
        name = m["username"]
        badge = c.chip("管理员", "amber") if m["is_admin"] else c.chip("成员", "cyan")
        phone = m["phone"] or "未绑定"
        pwd = m["password"] or "（无法解密）"
        pwd_show = pwd if show_pwd else "•" * 6

        with st.container(border=True):
            left, mid, right = st.columns([2.4, 2.2, 1.5])

            with left:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:11px">'
                    f'{_initial_block(name, m["is_admin"])}'
                    f"<div>"
                    f'<div style="font-weight:700;color:#fff;font-size:15px">'
                    f'{c.e(name)}　{badge}</div>'
                    f'<div style="color:#9BA3C7;font-size:12px;margin-top:3px">'
                    f'📱 {c.e(phone)}　·　注册 {c.e(m["created_at"][:10])}</div>'
                    f"</div></div>",
                    unsafe_allow_html=True,
                )

            with mid:
                st.markdown(
                    f'<div style="font-size:12.5px;color:#9BA3C7;line-height:2">'
                    f'密码：<span style="color:#FDE68A;font-family:ui-monospace,Consolas,monospace;'
                    f'letter-spacing:1.5px">{c.e(pwd_show)}</span><br>'
                    f'上次登录：{c.e(m["last_login"] or "从未登录")}</div>',
                    unsafe_allow_html=True,
                )

            with right:
                st.markdown(
                    f'<div style="font-size:12.5px;color:#9BA3C7;line-height:2">'
                    f'发帖 {m["posts"]}　获赞 {m["likes"]}<br>'
                    f'文件 {m["files"]}　草稿 {m["drafts"]}</div>',
                    unsafe_allow_html=True,
                )

            with st.expander("⚙ 管理操作", expanded=False):
                if m["is_admin"]:
                    st.caption("管理员账户受到保护，不能被删除。")
                a1, a2 = st.columns([1.4, 1])
                with a1:
                    new_pwd = st.text_input(
                        f"把 {name} 的密码重置为（{config.PASSWORD_LEN} 位数字）",
                        max_chars=config.PASSWORD_LEN,
                        key=f"respwd_{name}",
                    )
                    if st.button("重置密码", key=f"resbtn_{name}", use_container_width=True):
                        ok, msg = admin.reset_member_password(user, name, new_pwd)
                        st.toast(msg) if ok else st.error(msg)
                        if ok:
                            st.rerun()
                with a2:
                    if not m["is_admin"]:
                        confirm = st.checkbox(
                            "我确认删除该账户及其全部内容",
                            key=f"confirm_{name}",
                        )
                        if st.button(
                            "🗑 删除账户",
                            key=f"del_{name}",
                            use_container_width=True,
                            disabled=not confirm,
                        ):
                            ok, msg = admin.delete_member(user, name)
                            st.toast(msg) if ok else st.error(msg)
                            if ok:
                                st.rerun()
                    else:
                        st.caption("—")

    c.footer(
        "管理操作会立即生效并写入数据库。删除成员不可恢复，请谨慎操作。<br>"
        "密码可逆存储属于安全折衷，仅适合教学 / 内网小站使用。"
    )
