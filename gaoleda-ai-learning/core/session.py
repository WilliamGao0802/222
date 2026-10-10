"""「记住我」会话令牌：签发与校验。

安全模型
- Cookie 里只放 `用户名|签发时间|签名`，签名 = HMAC-SHA256(密钥, 用户名 + 签发时间)。
- 密钥在 core/crypto.py 里管理（data/.secret，不入库、不进 Git）。
- 校验时重算签名并做常量时间比较 → 没有密钥就无法伪造任何用户名。
- 令牌不含密码、与密码哈希无关；改密码不影响已签发令牌的有效性判断逻辑。
- 超过 SESSION_DAYS 自动失效；密钥文件丢失（如数据目录被重置）则全部令牌失效，
  用户重新登录一次即可，属于安全的失败方向。
"""

from __future__ import annotations

import time

from . import crypto
from .config import SESSION_DAYS

_SEP = "|"


def issue(username: str) -> str:
    """为某个用户签发一张令牌。"""
    name = (username or "").strip()
    if not name:
        return ""
    issued = int(time.time())
    return _SEP.join((name, str(issued), crypto.sign(f"{name}\n{issued}")))


def verify(token: str) -> str | None:
    """校验令牌；有效则返回用户名，否则返回 None。"""
    parts = (token or "").split(_SEP)
    if len(parts) != 3:
        return None
    name, issued_text, signature = parts
    if not name:
        return None
    try:
        issued = int(issued_text)
    except ValueError:
        return None
    if issued > time.time() + 300:          # 明显来自未来的令牌直接拒绝
        return None
    if time.time() - issued > max_age():
        return None
    if not crypto.verify_signature(f"{name}\n{issued}", signature):
        return None
    return name


def max_age() -> int:
    """Cookie 有效期（秒）。"""
    return SESSION_DAYS * 24 * 3600
