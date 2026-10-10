"""SQLite 持久化层 —— 全项目唯一的落盘入口。

设计要点
- 单文件 SQLite，随项目走，无需外部数据库（部署沙箱只给一个 HTTP 端口）。
- WAL 模式 + busy_timeout，容忍 Streamlit 的多线程并发脚本重跑。
- 连接用完即关，避免跨线程复用；写入用进程级锁串行化。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

from .config import DATA_DIR, DB_PATH

_LOCK = threading.RLock()
_initialized = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    last_login    TEXT,
    bio           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS posts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    content    TEXT NOT NULL,
    topic      TEXT NOT NULL DEFAULT '综合',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS likes (
    post_id    INTEGER NOT NULL,
    username   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (post_id, username)
);

CREATE TABLE IF NOT EXISTS follows (
    follower   TEXT NOT NULL,
    followee   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (follower, followee)
);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL,
    filename    TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    size        INTEGER NOT NULL DEFAULT 0,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_likes_post    ON likes(post_id);
CREATE INDEX IF NOT EXISTS idx_files_created ON files(created_at DESC);
"""


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """打开一个连接；正常退出自动提交，异常自动回滚。"""
    global _initialized

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        if not _initialized:
            with _LOCK:
                if not _initialized:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.executescript(SCHEMA)
                    conn.commit()
                    _initialized = True
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def write(fn):
    """装饰器：把一次写操作放进进程锁，避免并发写互相打断。"""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)

    return wrapper


def reset_for_tests() -> None:
    """仅供单元测试调用：清空所有表。"""
    global _initialized
    with _LOCK:
        with db() as conn:
            for table in ("likes", "follows", "files", "posts", "users"):
                conn.execute(f"DELETE FROM {table}")
        _initialized = True
