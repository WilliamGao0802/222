"""全局配置：路径、上限、常量。整个项目唯一的常量来源。"""

from __future__ import annotations

import os
from pathlib import Path

# ---------- 应用元信息 ----------
APP_NAME = "高乐达的AI学习"
APP_SLOGAN = "探索人工智能前沿 · 交流 · 成长"
VERSION = "1.0.0"

# ---------- 路径 ----------
ROOT = Path(__file__).resolve().parent.parent

# 允许用环境变量把运行数据挪到别处（测试、或挂载持久磁盘时使用）
_ENV_DATA_DIR = os.environ.get("GAOLEDA_DATA_DIR", "").strip()
DATA_DIR = Path(_ENV_DATA_DIR) if _ENV_DATA_DIR else (ROOT / "data")
DB_PATH = DATA_DIR / "app.db"
UPLOAD_DIR = DATA_DIR / "uploads"
NEWS_CACHE_PATH = DATA_DIR / "news_cache.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 用户系统 ----------
MAX_USERS = 1000          # 注册用户总数上限
PASSWORD_LEN = 6          # 密码必须恰好为 6 位阿拉伯数字
USERNAME_MIN = 2
USERNAME_MAX = 20

# ---------- 文件区 ----------
MAX_UPLOAD_MB = 20
ALLOWED_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".txt", ".md", ".csv", ".json", ".py", ".ipynb",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".zip", ".rar", ".7z", ".mp3", ".mp4",
}

# ---------- 讨论区 ----------
MAX_POST_LEN = 500

# ---------- 新闻 ----------
NEWS_TTL_SECONDS = 1800   # 30 分钟缓存，兼顾时效性与稳定性
NEWS_LIMIT = 5
NEWS_WINDOW_DAYS = 365    # 只保留近一年
