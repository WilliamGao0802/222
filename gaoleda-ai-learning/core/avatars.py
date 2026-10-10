"""头像：本地上传、读取、删除。

存储约定
- 图片文件落在 data/avatars/，用 uuid 重命名（绝不用客户端文件名做路径）。
- 数据库 users.avatar 只存文件名。
- 渲染时转成 data URI 内联进页面，因此不依赖任何静态文件服务。

性能
- 头像在讨论区会被反复渲染，所以按「存储文件名」做进程内缓存；
  文件名每次上传都会变，缓存天然随换头像而失效。
- 单张上限 AVATAR_MAX_KB（默认 300 KB），缓存规模可控。
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

from .config import AVATAR_DIR, AVATAR_MAX_KB, AVATAR_SUFFIXES
from .storage import db, write

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

_CACHE: dict[str, str] = {}
_CACHE_MAX = 200


def avatar_file(username: str) -> str:
    """取该用户头像的存储文件名；没设置则返回空串。"""
    with db() as conn:
        row = conn.execute(
            "SELECT avatar FROM users WHERE username = ?", ((username or "").strip(),)
        ).fetchone()
    return (row["avatar"] if row else "") or ""


def human_kb(num: int) -> str:
    return f"{num / 1024:.0f} KB"


@write
def save_avatar(username: str, filename: str, data: bytes) -> tuple[bool, str]:
    """保存 / 更换头像。成功后会删掉旧文件。"""
    name = (username or "").strip()
    if not name:
        return False, "请先登录后再设置头像"
    if not data:
        return False, "图片内容为空，请重新选择"

    size = len(data)
    if size > AVATAR_MAX_KB * 1024:
        return False, f"头像过大，请控制在 {AVATAR_MAX_KB} KB 以内（当前 {human_kb(size)}）"

    suffix = Path(filename or "").suffix.lower()
    if suffix not in AVATAR_SUFFIXES:
        return False, "头像仅支持 PNG / JPG / JPEG / GIF / WEBP / BMP 图片"

    with db() as conn:
        row = conn.execute("SELECT avatar FROM users WHERE username = ?", (name,)).fetchone()
        if row is None:
            return False, "用户不存在"
        old = row["avatar"] or ""

    stored = f"{uuid.uuid4().hex}{suffix}"
    try:
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        (AVATAR_DIR / stored).write_bytes(data)
    except Exception as exc:  # noqa: BLE001
        return False, f"保存头像失败：{exc}"

    with db() as conn:
        conn.execute("UPDATE users SET avatar = ? WHERE username = ?", (stored, name))

    if old:
        (AVATAR_DIR / Path(old).name).unlink(missing_ok=True)
        _CACHE.pop(old, None)
    return True, f"头像已更新（{human_kb(size)}）"


@write
def clear_avatar(username: str) -> tuple[bool, str]:
    """恢复默认头像（删除已上传的图片）。"""
    name = (username or "").strip()
    if not name:
        return False, "请先登录"
    old = avatar_file(name)
    with db() as conn:
        conn.execute("UPDATE users SET avatar = '' WHERE username = ?", (name,))
    if old:
        (AVATAR_DIR / Path(old).name).unlink(missing_ok=True)
        _CACHE.pop(old, None)
    return True, "已恢复默认头像"


def avatar_data_uri(username: str) -> str:
    """返回可内联进 <img src> 的 data URI；没有头像或读取失败时返回空串。"""
    stored = avatar_file(username)
    if not stored:
        return ""

    cached = _CACHE.get(stored)
    if cached is not None:
        return cached

    path = AVATAR_DIR / Path(stored).name
    try:
        raw = path.read_bytes()
    except Exception:  # noqa: BLE001  文件丢失（如数据目录被重置）
        return ""

    mime = _MIME.get(Path(stored).suffix.lower(), "image/png")
    uri = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")

    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[stored] = uri
    return uri
