"""「记住我」会话令牌：签发与校验。

安全模型
- Cookie 里只放 `用户名|签发时间|世代号|签名`，
  签名 = HMAC-SHA256(密钥, 用户名 + 签发时间 + 世代号)。
- 密钥在 core/crypto.py 里管理（data/.secret，不入库、不进 Git）。
- 校验时重算签名并做常量时间比较 → 没有密钥就无法伪造任何用户名。
- 令牌不含密码、与密码哈希无关；改密码不影响已签发令牌的有效性判断逻辑。
- 世代号（session_epoch）让「退出登录」具备服务端确定性：
  退出时把库里的世代号 +1，所有旧令牌立即失效，不依赖浏览器把 Cookie 删干净。
  代价是同一个人在多台设备登录时，任一处退出会让其余设备的「记住我」一并失效
  （对本站这种小范围社群场景是合理取舍）。
- 超过 SESSION_DAYS 自动失效；密钥文件丢失（如数据目录被重置）则全部令牌失效，
  用户重新登录一次即可，属于安全的失败方向。

为什么要 base64url 编码用户名（踩坑记录）
    令牌要原样塞进 Cookie。Streamlit 读 Cookie 走的是标准库 SimpleCookie，
    它**不做百分号解码**——而浏览器写 Cookie 时若用 encodeURIComponent，
    分隔符 `|` 会变成 `%7C`，回读后 verify 直接失败（现象：Cookie 明明写进去了，
    刷新却依然未登录）。中文用户名经 HTTP 头往返还会乱码。
    因此这里把用户名编成 urlsafe-base64（字母数字加 `-` `_`，无 `=` 填充），
    整个令牌就是纯 Cookie 安全 ASCII，浏览器与服务端能原样往返。
"""

from __future__ import annotations

import base64
import time

from . import crypto
from .config import SESSION_DAYS

_SEP = "|"


def _encode_name(name: str) -> str:
    """用户名 → Cookie 安全 ASCII（urlsafe-base64，去掉 `=` 填充）。"""
    return base64.urlsafe_b64encode(name.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_name(text: str) -> str | None:
    """还原用户名；不是合法编码时返回 None。"""
    try:
        padded = text + "=" * (-len(text) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001  任意脏数据都不该让页面崩溃
        return None


def issue(username: str, epoch: int = 0) -> str:
    """为某个用户签发一张令牌。`epoch` 为该用户当前的会话世代号。"""
    name = (username or "").strip()
    if not name:
        return ""
    issued = int(time.time())
    gen = int(epoch)
    return _SEP.join(
        (_encode_name(name), str(issued), str(gen), crypto.sign(f"{name}\n{issued}\n{gen}"))
    )


def verify(token: str) -> tuple[str, int] | None:
    """校验令牌；有效则返回 `(用户名, 会话世代号)`，否则返回 None。

    这里只做「签名 + 时效」校验，世代号是否仍然有效由调用方查库比对
    （core/auth.py 的 session_epoch），以保持本模块不依赖数据库。
    """
    parts = (token or "").split(_SEP)
    if len(parts) != 4:
        return None
    encoded_name, issued_text, epoch_text, signature = parts
    if not encoded_name:
        return None
    name = _decode_name(encoded_name)
    if not name:
        return None
    try:
        issued = int(issued_text)
        epoch = int(epoch_text)
    except ValueError:
        return None
    if issued > time.time() + 300:          # 明显来自未来的令牌直接拒绝
        return None
    if time.time() - issued > max_age():
        return None
    if not crypto.verify_signature(f"{name}\n{issued}\n{epoch}", signature):
        return None
    return name, epoch


def max_age() -> int:
    """Cookie 有效期（秒）。"""
    return SESSION_DAYS * 24 * 3600
