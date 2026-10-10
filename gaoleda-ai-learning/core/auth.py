"""用户系统：注册 / 登录 / 退出所需的一切业务逻辑。

规则（来自需求）
- 用户名 + 密码即可注册、登录，无邮箱、无手机号。
- 密码必须**恰好 6 位阿拉伯数字**，逐项给出明确错误提示。
- 用户名唯一；注册总人数上限 1000。
- 密码不落明文：PBKDF2-HMAC-SHA256 + 每用户随机盐。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Any

from .config import MAX_USERS, PASSWORD_LEN, USERNAME_MAX, USERNAME_MIN
from .storage import db, write

_ITERATIONS = 120_000
_FORBIDDEN_NAME_CHARS = set(" \t\n\r@/\\\"'<>#")


# ---------------------------------------------------------------- 校验
def validate_username(username: str) -> tuple[bool, str]:
    name = (username or "").strip()
    if not name:
        return False, "用户名不能为空"
    if len(name) < USERNAME_MIN:
        return False, f"用户名至少 {USERNAME_MIN} 个字符"
    if len(name) > USERNAME_MAX:
        return False, f"用户名最多 {USERNAME_MAX} 个字符（当前 {len(name)} 个）"
    if any(ch in _FORBIDDEN_NAME_CHARS for ch in name):
        return False, "用户名不能包含空格或 @ / \\ \" ' < > # 等特殊符号"
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    pwd = password or ""
    if not pwd:
        return False, "密码不能为空"
    if not pwd.isascii() or not pwd.isdigit():
        return False, "密码只能由 0-9 的阿拉伯数字组成，不能含字母、符号或全角数字"
    if len(pwd) != PASSWORD_LEN:
        return False, f"密码必须恰好为 {PASSWORD_LEN} 位数字（当前输入 {len(pwd)} 位）"
    return True, ""


# ---------------------------------------------------------------- 哈希
def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    )
    return dk.hex()


def _make_stored(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}${_hash_password(password, salt)}"


def _verify(stored: str, password: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    calc = _hash_password(password, salt)
    return hmac.compare_digest(calc, digest)


# ---------------------------------------------------------------- 查询
def user_count() -> int:
    with db() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])


def user_exists(username: str) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", ((username or "").strip(),)
        ).fetchone()
    return row is not None


def get_user(username: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT username, created_at, last_login, bio FROM users WHERE username = ?",
            ((username or "").strip(),),
        ).fetchone()
    return dict(row) if row else None


def list_users(limit: int = 200) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT username, created_at, last_login FROM users ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def remaining_slots() -> int:
    return max(0, MAX_USERS - user_count())


# ---------------------------------------------------------------- 写操作
@write
def register(username: str, password: str) -> tuple[bool, str]:
    ok, msg = validate_username(username)
    if not ok:
        return False, msg
    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    name = username.strip()
    with db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone():
            return False, "该用户名已被注册，请换一个"
        total = int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])
        if total >= MAX_USERS:
            return False, f"注册用户已达上限（{MAX_USERS} 人），暂时无法注册新账号"
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at, last_login) "
            "VALUES (?, ?, ?, NULL)",
            (name, _make_stored(password), datetime.now().isoformat(timespec="seconds")),
        )
    return True, "注册成功，请使用刚刚的用户名和密码登录"


@write
def login(username: str, password: str) -> tuple[bool, str]:
    ok, msg = validate_username(username)
    if not ok:
        return False, msg
    ok, msg = validate_password(password)
    if not ok:
        return False, msg

    name = username.strip()
    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (name,)
        ).fetchone()
        if row is None:
            return False, "用户不存在，请先注册"
        if not _verify(row["password_hash"], password):
            return False, "密码错误，请重新输入"
        conn.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (datetime.now().isoformat(timespec="seconds"), name),
        )
    return True, f"欢迎回来，{name}"


@write
def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    name = (username or "").strip()
    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (name,)
        ).fetchone()
        if row is None:
            return False, "用户不存在"
        if not _verify(row["password_hash"], old_password or ""):
            return False, "原密码错误"
        ok, msg = validate_password(new_password)
        if not ok:
            return False, msg
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (_make_stored(new_password), name),
        )
    return True, "密码已更新"


@write
def set_bio(username: str, bio: str) -> tuple[bool, str]:
    text = (bio or "").strip()[:80]
    with db() as conn:
        conn.execute("UPDATE users SET bio = ? WHERE username = ?", (text, username))
    return True, "个人简介已保存"
