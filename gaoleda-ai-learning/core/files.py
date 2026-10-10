"""文件区：从本地选择文件上传、浏览、下载、删除。

安全约定
- 绝不使用客户端传来的文件名作为磁盘路径：一律用 uuid 重命名落盘，
  原始文件名只作为数据库里的一列展示。
- 限制扩展名白名单与单文件大小，拒绝空文件。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ALLOWED_SUFFIXES, MAX_UPLOAD_MB, UPLOAD_DIR
from .storage import db, write

_SAFE_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


def human_size(num: int) -> str:
    step = 1024.0
    value = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < step or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} GB"


def sanitize_filename(name: str) -> str:
    base = Path(name or "未命名文件").name
    base = _SAFE_RE.sub("_", base).strip().strip(".")
    if not base:
        base = "未命名文件"
    if len(base) > 80:
        stem, dot, suffix = base.rpartition(".")
        base = (stem[:70] + dot + suffix[:8]) if dot else base[:80]
    return base


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@write
def save_upload(
    username: str, filename: str, data: bytes, note: str = ""
) -> tuple[bool, str]:
    name = (username or "").strip()
    if not name:
        return False, "请先登录后再上传文件"
    if not data:
        return False, "文件为空，请重新选择"

    size = len(data)
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        return False, f"文件过大，单个文件上限 {MAX_UPLOAD_MB} MB（当前 {human_size(size)}）"

    safe = sanitize_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return False, f"不支持的文件类型「{suffix or '无扩展名'}」，请上传文档、图片、代码或压缩包"

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / stored_name
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except Exception as exc:  # noqa: BLE001
        return False, f"写入磁盘失败：{exc}"

    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO files (username, filename, stored_name, size, note, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, safe, stored_name, size, (note or "").strip()[:80], _now()),
            )
    except Exception as exc:  # noqa: BLE001
        target.unlink(missing_ok=True)
        return False, f"登记文件失败：{exc}"

    return True, f"上传成功：{safe}（{human_size(size)}）"


def list_files(limit: int = 200, username: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT id, username, filename, stored_name, size, note, created_at FROM files"
    params: list[Any] = []
    if username:
        sql += " WHERE username = ?"
        params.append(username)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["size_human"] = human_size(item["size"])
        item["path"] = UPLOAD_DIR / item["stored_name"]
        out.append(item)
    return out


def count_files() -> int:
    with db() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"])


def total_size() -> int:
    with db() as conn:
        row = conn.execute("SELECT COALESCE(SUM(size), 0) AS s FROM files").fetchone()
    return int(row["s"])


def read_file(stored_name: str) -> bytes | None:
    path = UPLOAD_DIR / Path(stored_name).name
    try:
        return path.read_bytes()
    except Exception:
        return None


@write
def delete_file(file_id: int, username: str) -> tuple[bool, str]:
    with db() as conn:
        row = conn.execute(
            "SELECT username, stored_name, filename FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if row is None:
            return False, "文件不存在或已被删除"
        if row["username"] != username:
            return False, "只能删除自己上传的文件"
        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    (UPLOAD_DIR / row["stored_name"]).unlink(missing_ok=True)
    return True, f"已删除：{row['filename']}"


def files_by(username: str) -> list[dict[str, Any]]:
    return list_files(username=username)
