"""讨论区：发帖、点赞、关注。

规则
- 仅注册用户可发言；点赞与关注同样要求登录（UI 层拦截，core 层再校验一次）。
- 点赞是「互赞」关系：同一用户对同一帖只有 0/1 两个状态，可取消。
- 关注是单向关系，可取消；不允许关注自己。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .config import MAX_POST_LEN
from .storage import db, write

TOPICS = ["综合", "大模型", "智能体", "具身智能", "算力芯片", "AI 治理", "学习方法"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- 帖子
@write
def add_post(username: str, content: str, topic: str = "综合") -> tuple[bool, str]:
    name = (username or "").strip()
    if not name:
        return False, "请先登录后再发言"
    text = (content or "").strip()
    if not text:
        return False, "发言内容不能为空"
    if len(text) > MAX_POST_LEN:
        return False, f"内容过长，请控制在 {MAX_POST_LEN} 字以内（当前 {len(text)} 字）"
    if topic not in TOPICS:
        topic = "综合"
    with db() as conn:
        conn.execute(
            "INSERT INTO posts (username, content, topic, created_at) VALUES (?, ?, ?, ?)",
            (name, text, topic, _now()),
        )
    return True, "发布成功"


def list_posts(limit: int = 100, offset: int = 0, viewer: str | None = None,
               topic: str | None = None, only_following: bool = False) -> list[dict[str, Any]]:
    sql = """
        SELECT p.id, p.username, p.content, p.topic, p.created_at,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS like_count
        FROM posts p
    """
    params: list[Any] = []
    where: list[str] = []
    if topic and topic != "全部":
        where.append("p.topic = ?")
        params.append(topic)
    if only_following and viewer:
        where.append(
            "p.username IN (SELECT followee FROM follows WHERE follower = ?)"
        )
        params.append(viewer)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
        liked: set[int] = set()
        following: set[str] = set()
        if viewer:
            liked = {
                r["post_id"]
                for r in conn.execute(
                    "SELECT post_id FROM likes WHERE username = ?", (viewer,)
                ).fetchall()
            }
            following = {
                r["followee"]
                for r in conn.execute(
                    "SELECT followee FROM follows WHERE follower = ?", (viewer,)
                ).fetchall()
            }

    out = []
    for r in rows:
        item = dict(r)
        item["liked_by_me"] = item["id"] in liked
        item["followed_by_me"] = item["username"] in following
        out.append(item)
    return out


def count_posts() -> int:
    with db() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"])


def posts_by(username: str, limit: int = 50) -> list[dict[str, Any]]:
    return [p for p in list_posts(limit=200) if p["username"] == username][:limit]


@write
def delete_post(post_id: int, username: str) -> tuple[bool, str]:
    with db() as conn:
        row = conn.execute("SELECT username FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            return False, "该发言不存在或已被删除"
        if row["username"] != username:
            return False, "只能删除自己的发言"
        conn.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return True, "已删除"


# ---------------------------------------------------------------- 点赞
@write
def toggle_like(post_id: int, username: str) -> tuple[bool, str, int]:
    name = (username or "").strip()
    if not name:
        return False, "请先登录后再点赞", 0
    with db() as conn:
        if conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone() is None:
            return False, "该发言不存在", 0
        hit = conn.execute(
            "SELECT 1 FROM likes WHERE post_id = ? AND username = ?", (post_id, name)
        ).fetchone()
        if hit:
            conn.execute(
                "DELETE FROM likes WHERE post_id = ? AND username = ?", (post_id, name)
            )
            msg = "已取消点赞"
        else:
            conn.execute(
                "INSERT INTO likes (post_id, username, created_at) VALUES (?, ?, ?)",
                (post_id, name, _now()),
            )
            msg = "点赞成功"
        total = int(
            conn.execute(
                "SELECT COUNT(*) AS c FROM likes WHERE post_id = ?", (post_id,)
            ).fetchone()["c"]
        )
    return True, msg, total


def who_liked(post_id: int) -> list[str]:
    with db() as conn:
        rows = conn.execute(
            "SELECT username FROM likes WHERE post_id = ?", (post_id,)
        ).fetchall()
    return [r["username"] for r in rows]


# ---------------------------------------------------------------- 关注
@write
def toggle_follow(follower: str, followee: str) -> tuple[bool, str, bool]:
    me = (follower or "").strip()
    other = (followee or "").strip()
    if not me:
        return False, "请先登录后再关注", False
    if me == other:
        return False, "不能关注自己", False
    with db() as conn:
        hit = conn.execute(
            "SELECT 1 FROM follows WHERE follower = ? AND followee = ?", (me, other)
        ).fetchone()
        if hit:
            conn.execute(
                "DELETE FROM follows WHERE follower = ? AND followee = ?", (me, other)
            )
            return True, f"已取消关注 {other}", False
        conn.execute(
            "INSERT INTO follows (follower, followee, created_at) VALUES (?, ?, ?)",
            (me, other, _now()),
        )
    return True, f"已关注 {other}", True


def following_of(username: str) -> list[str]:
    with db() as conn:
        rows = conn.execute(
            "SELECT followee FROM follows WHERE follower = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
    return [r["followee"] for r in rows]


def followers_of(username: str) -> list[str]:
    with db() as conn:
        rows = conn.execute(
            "SELECT follower FROM follows WHERE followee = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
    return [r["follower"] for r in rows]


def is_following(follower: str, followee: str) -> bool:
    if not follower:
        return False
    with db() as conn:
        return (
            conn.execute(
                "SELECT 1 FROM follows WHERE follower = ? AND followee = ?",
                (follower, followee),
            ).fetchone()
            is not None
        )


def active_users(limit: int = 8) -> list[dict[str, Any]]:
    """按「发帖数 + 被点赞数」排序的活跃用户榜。"""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.username,
                   COALESCE(p.cnt, 0) AS posts,
                   COALESCE(l.cnt, 0) AS likes
            FROM users u
            LEFT JOIN (SELECT username, COUNT(*) cnt FROM posts GROUP BY username) p
                   ON p.username = u.username
            LEFT JOIN (
                SELECT po.username, COUNT(*) cnt
                FROM likes li JOIN posts po ON po.id = li.post_id
                GROUP BY po.username
            ) l ON l.username = u.username
            ORDER BY (COALESCE(p.cnt,0) * 2 + COALESCE(l.cnt,0)) DESC, u.created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
