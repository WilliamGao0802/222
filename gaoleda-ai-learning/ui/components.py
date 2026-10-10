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


def list_item(name: str, sub: str, right: str = "") -> None:
    right_html = f'<div class="g-sub" style="white-space:nowrap">{right}</div>' if right else ""
    html(
        f"""
        <div class="g-list-item">
            <div>
                <div class="g-name">{e(name)}</div>
                <div class="g-sub">{e(sub)}</div>
            </div>
            {right_html}
        </div>
        """
    )


def user_box(name: str, sub: str) -> None:
    html(
        f"""
        <div class="g-userbox">
            <div class="g-uname">{e(name)}</div>
            <div class="g-usub">{e(sub)}</div>
        </div>
        """
    )


def footer(text: str) -> None:
    html(f'<div class="g-foot">{text}</div>')
