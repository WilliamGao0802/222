"""全局配置：路径、上限、常量。整个项目唯一的常量来源。"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ---------- 应用元信息 ----------
APP_NAME = "学习AI with William Gao"
APP_SLOGAN = "探索人工智能前沿 · 交流 · 成长"
VERSION = "1.1.0"

# ---------- 路径 ----------
ROOT = Path(__file__).resolve().parent.parent

# 允许用环境变量把运行数据挪到别处（测试、或挂载持久磁盘时使用）
_ENV_DATA_DIR = os.environ.get("GAOLEDA_DATA_DIR", "").strip()
DATA_DIR = Path(_ENV_DATA_DIR) if _ENV_DATA_DIR else (ROOT / "data")
DB_PATH = DATA_DIR / "app.db"
UPLOAD_DIR = DATA_DIR / "uploads"
AVATAR_DIR = DATA_DIR / "avatars"
NEWS_CACHE_PATH = DATA_DIR / "news_cache.json"
# 会话签名 / 密码可逆存储共用的密钥文件（自动生成，不入库、不进 Git）
SECRET_PATH = DATA_DIR / ".secret"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# ---------- 用户系统 ----------
MAX_USERS = 1000          # 注册用户总数上限
PASSWORD_LEN = 6          # 密码必须恰好为 6 位阿拉伯数字
USERNAME_MIN = 2
USERNAME_MAX = 20

# 管理员用户名（不区分大小写）。以这些名字注册的账号自动获得管理员权限。
ADMIN_USERNAMES = {"william"}

# 手机号：中国大陆 11 位，1 开头、第二位 3-9，无需短信验证码
PHONE_PATTERN = r"^1[3-9]\d{9}$"
PHONE_RE = re.compile(PHONE_PATTERN)

# ---------- 登录状态（记住我） ----------
SESSION_COOKIE = "gaoleda_session"
SESSION_DAYS = 30         # Cookie 有效期（天）

# ---------- 头像 ----------
AVATAR_MAX_KB = 300
AVATAR_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# ---------- 文件区 ----------
MAX_UPLOAD_MB = 20
ALLOWED_SUFFIXES = {
    # 文档
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".txt", ".md", ".csv", ".json", ".xml", ".yml", ".yaml", ".toml",
    # 图片
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
    # 代码（「算法 / 题解」仓库常用）
    ".py", ".ipynb", ".cpp", ".cc", ".c", ".h", ".hpp", ".java",
    ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb", ".php",
    ".sql", ".sh", ".bat", ".r", ".m", ".kt", ".swift",
    # 压缩包与音视频
    ".zip", ".rar", ".7z", ".tar", ".gz", ".mp3", ".mp4",
}

# 文件仓库分类：上传时必须选一个，浏览时可按仓库筛选
FILE_REPOS = ["算法", "文章", "语法", "题解"]
DEFAULT_REPO = FILE_REPOS[0]
ALL_REPOS = "全部"

# ---------- 讨论区 ----------
MAX_POST_LEN = 500
MAX_DRAFT_LEN = 500       # 草稿箱单条上限

# ---------- 新闻 ----------
NEWS_TTL_SECONDS = 1800   # 30 分钟缓存，兼顾时效性与稳定性
NEWS_LIMIT = 5
NEWS_WINDOW_DAYS = 365    # 只保留近一年
