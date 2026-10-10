"""可复用 UI 组件：全部返回 HTML 片段，统一走 st.markdown(unsafe_allow_html=True)。

安全：所有来自用户输入的内容都经过 html.escape，避免 XSS 与版面被撑破。
"""

from __future__ import annotations

from html import escape

import streamlit as st


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def e(text: object) -> str:
    return escape(str(text if text is not None else ""), quote=True)


def chip(text: str, kind: str = "") -> str:
    cls = f"g-chip {kind}".strip()
    return f'<span class="{cls}">{e(text)}</span>'


# ---------------------------------------------------------------- 头像
def avatar_block(username: str, size: int = 38) -> str:
    """圆形头像 HTML：上传过就显示图片，否则显示首字母渐变块。"""
    from core import avatars  # 延迟导入，避免 ui → core 的模块级耦合

    name = (username or "?").strip() or "?"
    uri = avatars.avatar_data_uri(name)
    if uri:
        return (
            f'<img src="{uri}" alt="{e(name)}" '
            f'style="width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;'
            f'flex:0 0 {size}px;display:block;border:1px solid rgba(255,255,255,.18)">'
        )
    initial = e(name[0].upper())
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;flex:0 0 {size}px;'
        f'display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;'
        f'font-size:{max(12, size // 2)}px;'
        f'background:linear-gradient(135deg,#7C6CF6,#22D3EE)">{initial}</div>'
    )


def hero(kicker: str, title: str, subtitle: str) -> None:
    html(
        f"""
        <div class="g-hero">
            <div class="g-kicker">{e(kicker)}</div>
            <h1>{e(title)}</h1>
            <p>{e(subtitle)}</p>
        </div>
        """
    )


def card(title: str, meta: str, body: str, index: int | None = None,
         link: str | None = None) -> None:
    badge = f'<span class="g-index">{index}</span>' if index is not None else ""
    link_html = (
        f'<a href="{e(link)}" target="_blank" rel="noopener noreferrer">阅读原文 →</a>'
        if link
        else ""
    )
    html(
        f"""
        <div class="g-card">
            <h3>{badge}{e(title)}</h3>
            <div class="g-meta">{meta}</div>
            <p class="g-body">{e(body)}</p>
            <div class="g-meta" style="margin-top:10px">{link_html}</div>
        </div>
        """
    )


def empty(emoji: str, text: str) -> None:
    html(
        f'<div class="g-empty"><span class="g-emo">{e(emoji)}</span>{e(text)}</div>'
    )


def list_item(name: str, sub: str, right: str = "", avatar: str = "") -> None:
    """一行信息。avatar 传用户名即渲染头像，传空串则只有文字。"""
    right_html = f'<div class="g-sub" style="white-space:nowrap">{right}</div>' if right else ""
    avatar_html = (
        f'<div style="flex:0 0 auto">{avatar_block(avatar, 34)}</div>' if avatar else ""
    )
    html(
        f"""
        <div class="g-list-item">
            <div style="display:flex;align-items:center;gap:11px;min-width:0">
                {avatar_html}
                <div style="min-width:0">
                    <div class="g-name">{e(name)}</div>
                    <div class="g-sub">{e(sub)}</div>
                </div>
            </div>
            {right_html}
        </div>
        """
    )


def user_box(name: str, sub: str, avatar: bool = True) -> None:
    av = (
        f'<div style="flex:0 0 auto">{avatar_block(name, 40)}</div>' if avatar else ""
    )
    html(
        f"""
        <div class="g-userbox">
            <div style="display:flex;align-items:center;gap:12px">
                {av}
                <div style="min-width:0">
                    <div class="g-uname">{e(name)}</div>
                    <div class="g-usub">{e(sub)}</div>
                </div>
            </div>
        </div>
        """
    )


def footer(text: str) -> None:
    html(f'<div class="g-foot">{text}</div>')
