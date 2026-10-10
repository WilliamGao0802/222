"""文件区：按仓库分类上传、浏览、搜索、下载、删除。

安全约定
- 绝不使用客户端传来的文件名作为磁盘路径：一律用 uuid 重命名落盘，
  原始文件名只作为数据库里的一列展示。
- 限制扩展名白名单与单文件大小，拒绝空文件。

仓库
- 上传时必须选一个仓库（config.FILE_REPOS：算法 / 文章 / 语法 / 题解）。
- 浏览时可按仓库筛选，并用站内搜索引擎检索文件名、说明、上传者。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    ALLOWED_SUFFIXES,
    ALL_REPOS,
    DEFAULT_REPO,
    FILE_REPOS,
    MAX_UPLOAD_MB,
    UPLOAD_DIR,
)
from .storage import db, write

_SAFE_RE = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")

# 搜索范围：键用于逻辑，值用于界面
SEARCH_SCOPES = {
    "all": "全部字段",
    "filename": "文件名",
    "note": "文件说明",
    "uploader": "上传者",
}

# 排序方式
ORDERINGS = {
    "new": "最新上传",
    "old": "最早上传",
    "name": "文件名 A→Z",
    "size": "文件大小",
}

_ORDER_SQL = {
    "new": "id DESC",
    "old": "id ASC",
    "name": "filename COLLATE NOCASE ASC",
    "size": "size DESC, id DESC",
}


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


def normalize_repo(repo: str) -> str:
    value = (repo or "").strip()
    return value if value in FILE_REPOS else DEFAULT_REPO


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- 上传
@write
def save_upload(
    username: str,
    filename: str,
    data: bytes,
    note: str = "",
    repo: str = DEFAULT_REPO,
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
                "INSERT INTO files (username, filename, stored_name, size, note, repo, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, safe, stored_name, size, (note or "").strip()[:80],
                 normalize_repo(repo), _now()),
            )
    except Exception as exc:  # noqa: BLE001
        target.unlink(missing_ok=True)
        return False, f"登记文件失败：{exc}"

    return True, f"上传成功：{safe}（{human_size(size)}）→ 已归入「{normalize_repo(repo)}」仓库"


# ---------------------------------------------------------------- 查询
def list_files(limit: int = 200, username: str | None = None) -> list[dict[str, Any]]:
    return search_files(limit=limit, username=username)


def _build_where(
    keyword: str, scope: str, repo: str | None, username: str | None
) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []

    if username:
        where.append("username = ?")
        params.append(username)
    if repo and repo != ALL_REPOS:
        where.append("repo = ?")
        params.append(repo)

    terms = [t for t in (keyword or "").lower().split() if t]
    if terms:
        columns = {
            "filename": ["filename"],
            "note": ["note"],
            "uploader": ["username"],
            "all": ["filename", "note", "username", "repo"],
        }.get(scope, ["filename", "note", "username", "repo"])
        for term in terms:                      # 多个关键词之间是「与」关系
            ors = " OR ".join(f"LOWER({col}) LIKE ?" for col in columns)
            where.append(f"({ors})")
            params.extend([f"%{term}%"] * len(columns))

    return where, params


def search_files(
    keyword: str = "",
    scope: str = "all",
    repo: str | None = None,
    order: str = "new",
    limit: int = 200,
    username: str | None = None,
) -> list[dict[str, Any]]:
    """站内搜索引擎：关键词（空格分隔、多词「与」）+ 范围 + 仓库 + 排序。"""
    where, params = _build_where(keyword, scope, repo, username)

    sql = (
        "SELECT id, username, filename, stored_name, size, note, repo, created_at FROM files"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY " + _ORDER_SQL.get(order, _ORDER_SQL["new"]) + " LIMIT ?"
    params.append(limit)

    with db() as conn:
        rows = conn.execute(sql, params).fetchall()

    out = []
    for r in rows:
        item = dict(r)
        item["size_human"] = human_size(item["size"])
        item["repo"] = item["repo"] or DEFAULT_REPO
        item["path"] = UPLOAD_DIR / item["stored_name"]
        out.append(item)
    return out


def count_files() -> int:
    with db() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"])


def repo_counts() -> dict[str, int]:
    """各仓库的文件数量，用于界面上的统计标签。"""
    counts = {repo: 0 for repo in FILE_REPOS}
    with db() as conn:
        rows = conn.execute("SELECT repo, COUNT(*) AS c FROM files GROUP BY repo").fetchall()
    for row in rows:
        counts[normalize_repo(row["repo"])] = int(row["c"])
    return counts


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


# ---------------------------------------------------------------- 删除
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
