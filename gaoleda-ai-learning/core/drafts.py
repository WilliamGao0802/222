"""讨论区草稿箱：把没写完的发言先存起来，随时载入、发布或删除。

规则
- 草稿属于创建者，只有本人能查看 / 修改 / 删除。
- 内容长度与正式发言同口径（MAX_DRAFT_LEN），超限直接拒收。
- 同一条草稿重复保存是「更新」而非新建（靠 draft_id 区分）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import MAX_DRAFT_LEN
from .discussion import TOPICS
from .storage import db, write


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _normalize_topic(topic: str) -> str:
    return topic if topic in TOPICS else TOPICS[0]


# ---------------------------------------------------------------- 查询
def count_drafts(username: str) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM drafts WHERE username = ?",
            ((username or "").strip(),),
        ).fetchone()
    return int(row["c"])


def list_drafts(username: str, limit: int = 50) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, content, topic, created_at, updated_at FROM drafts "
            "WHERE username = ? ORDER BY id DESC LIMIT ?",
            ((username or "").strip(), limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_draft(draft_id: int, username: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT id, content, topic, created_at, updated_at FROM drafts "
            "WHERE id = ? AND username = ?",
            (draft_id, (username or "").strip()),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------- 写操作
@write
def save_draft(
    username: str,
    content: str,
    topic: str = TOPICS[0],
    draft_id: int | None = None,
) -> tuple[bool, str, int | None]:
    """新建或更新草稿。返回 (是否成功, 提示, 草稿 id)。"""
    name = (username or "").strip()
    if not name:
        return False, "请先登录后再保存草稿", None

    text = (content or "").strip()
    if not text:
        return False, "草稿内容不能为空", None
    if len(text) > MAX_DRAFT_LEN:
        return False, f"草稿过长，请控制在 {MAX_DRAFT_LEN} 字以内（当前 {len(text)} 字）", None

    topic_value = _normalize_topic(topic)

    with db() as conn:
        if draft_id is not None:
            row = conn.execute(
                "SELECT id FROM drafts WHERE id = ? AND username = ?", (draft_id, name)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE drafts SET content = ?, topic = ?, updated_at = ? WHERE id = ?",
                    (text, topic_value, _now(), draft_id),
                )
                return True, f"草稿 #{draft_id} 已更新", draft_id

        cur = conn.execute(
            "INSERT INTO drafts (username, content, topic, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, text, topic_value, _now(), _now()),
        )
        new_id = int(cur.lastrowid)
    return True, f"已存入草稿箱（草稿 #{new_id}）", new_id


@write
def delete_draft(draft_id: int, username: str) -> tuple[bool, str]:
    name = (username or "").strip()
    if not name:
        return False, "请先登录"
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM drafts WHERE id = ? AND username = ?", (draft_id, name)
        ).fetchone()
        if row is None:
            return False, "草稿不存在或已被删除"
        conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    return True, f"已删除草稿 #{draft_id}"


@write
def clear_drafts(username: str) -> tuple[bool, str]:
    name = (username or "").strip()
    if not name:
        return False, "请先登录"
    with db() as conn:
        cur = conn.execute("DELETE FROM drafts WHERE username = ?", (name,))
        removed = cur.rowcount or 0
    return True, f"已清空 {removed} 条草稿"
