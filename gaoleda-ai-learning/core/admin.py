"""管理员后台的业务逻辑：成员总览、密码查看、账户删除。

权限模型
- 只有 users.role = 'admin' 的账号才能调用这里的写操作；
  用户名命中 config.ADMIN_USERNAMES 的账号在注册时自动获得该角色。
- 每个写操作都重新校验一次调用者身份（不依赖 UI 层的隐藏）。

关于「查看密码」
- 登录校验用的是 PBKDF2 哈希，不可逆；
- 因此注册/改密时额外用 core/crypto.py 存了一份可逆加密副本供管理员查看。
  这是明显的安全折衷，仅适合教学 / 内网小站。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import auth, avatars, crypto
from . import files as file_store
from .config import ADMIN_USERNAMES
from .storage import db, write


# ---------------------------------------------------------------- 权限
def is_admin(username: str) -> bool:
    """查询数据库判断角色（不依赖用户名白名单，便于手工授予）。"""
    name = (username or "").strip()
    if not name:
        return False
    with db() as conn:
        row = conn.execute("SELECT role FROM users WHERE username = ?", (name,)).fetchone()
    return bool(row) and row["role"] == auth.ROLE_ADMIN


@write
def sync_admin_roles() -> int:
    """把用户名命中 ADMIN_USERNAMES 的老账号提升为管理员，返回受影响行数。

    每次进程启动同步一次即可，解决「账号在管理员名单生效前就已注册」的情况。
    """
    promoted = 0
    with db() as conn:
        for name in ADMIN_USERNAMES:
            cur = conn.execute(
                "UPDATE users SET role = ? WHERE LOWER(username) = ? AND role != ?",
                (auth.ROLE_ADMIN, name, auth.ROLE_ADMIN),
            )
            promoted += cur.rowcount or 0
    return promoted


# ---------------------------------------------------------------- 成员总览
def _member_rows(keyword: str = "") -> list[dict[str, Any]]:
    sql = """
        SELECT u.username, u.role, u.phone, u.avatar, u.bio,
               u.created_at, u.last_login, u.password_enc,
               (SELECT COUNT(*) FROM posts  p WHERE p.username = u.username) AS posts,
               (SELECT COUNT(*) FROM files  f WHERE f.username = u.username) AS files,
               (SELECT COUNT(*) FROM drafts d WHERE d.username = u.username) AS drafts,
               COALESCE((
                   SELECT COUNT(*) FROM likes l
                   JOIN posts p2 ON p2.id = l.post_id
                   WHERE p2.username = u.username
               ), 0) AS likes
        FROM users u
        ORDER BY (u.role = 'admin') DESC, u.created_at ASC
    """
    with db() as conn:
        rows = conn.execute(sql).fetchall()

    kw = (keyword or "").strip().lower()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["password"] = crypto.decrypt(item.pop("password_enc", "") or "")
        item["is_admin"] = item["role"] == auth.ROLE_ADMIN
        if kw and kw not in item["username"].lower() and kw not in (item["phone"] or ""):
            continue
        out.append(item)
    return out


def list_members(keyword: str = "") -> list[dict[str, Any]]:
    """成员列表（含解密后的密码）。调用方负责确认操作者是管理员。"""
    return _member_rows(keyword)


def stats() -> dict[str, int]:
    with db() as conn:
        one = lambda sql: int(conn.execute(sql).fetchone()[0])  # noqa: E731
        return {
            "members": one("SELECT COUNT(*) FROM users"),
            "admins": one("SELECT COUNT(*) FROM users WHERE role = 'admin'"),
            "posts": one("SELECT COUNT(*) FROM posts"),
            "files": one("SELECT COUNT(*) FROM files"),
            "drafts": one("SELECT COUNT(*) FROM drafts"),
        }


# ---------------------------------------------------------------- 删除成员
@write
def delete_member(operator: str, target: str) -> tuple[bool, str]:
    """删除成员账户，并级联清理其全部内容（发言、点赞、关注、草稿、上传文件、头像）。"""
    op = (operator or "").strip()
    who = (target or "").strip()

    if not is_admin(op):
        return False, "只有管理员可以删除成员账户"
    if not who:
        return False, "请先指定要删除的成员"
    if who == op:
        return False, "不能删除当前登录的管理员账户"

    with db() as conn:
        row = conn.execute(
            "SELECT role, avatar FROM users WHERE username = ?", (who,)
        ).fetchone()
        if row is None:
            return False, "该成员不存在或已被删除"
        if row["role"] == auth.ROLE_ADMIN:
            return False, "不能删除管理员账户，请先解除其管理员身份"

        stored_files = [
            r["stored_name"]
            for r in conn.execute(
                "SELECT stored_name FROM files WHERE username = ?", (who,)
            ).fetchall()
        ]
        avatar = row["avatar"] or ""

        conn.execute("DELETE FROM likes WHERE username = ?", (who,))
        conn.execute(
            "DELETE FROM likes WHERE post_id IN (SELECT id FROM posts WHERE username = ?)",
            (who,),
        )
        conn.execute("DELETE FROM follows WHERE follower = ? OR followee = ?", (who, who))
        conn.execute("DELETE FROM drafts WHERE username = ?", (who,))
        conn.execute("DELETE FROM files WHERE username = ?", (who,))
        conn.execute("DELETE FROM posts WHERE username = ?", (who,))
        conn.execute("DELETE FROM users WHERE username = ?", (who,))

    for name in stored_files:
        (file_store.UPLOAD_DIR / Path(name).name).unlink(missing_ok=True)
    if avatar:
        (avatars.AVATAR_DIR / Path(avatar).name).unlink(missing_ok=True)

    return True, f"已删除成员 {who}，其发言 / 点赞 / 关注 / 草稿 / 文件一并清理"


@write
def reset_member_password(operator: str, target: str, new_password: str) -> tuple[bool, str]:
    """管理员直接把成员密码重置为指定值。"""
    op = (operator or "").strip()
    who = (target or "").strip()
    if not is_admin(op):
        return False, "只有管理员可以重置密码"
    ok, msg = auth.reset_password(who, new_password)
    return (True, f"已把 {who} 的密码重置为 {new_password}") if ok else (False, msg)
