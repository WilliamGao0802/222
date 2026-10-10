"""密钥与对称加密小工具（标准库实现，零第三方依赖）。

用途
- `secret_key()`：为「记住登录」的 Cookie 签名提供密钥。
- `encrypt()/decrypt()`：为管理员后台「查看成员密码」提供可逆存储。

为什么不只用哈希
    用户登录校验走 PBKDF2 哈希（不可逆）——这是安全的正确做法。
    但管理员需要看到成员密码，哈希无法还原，所以必须另存一份可逆副本。

坦白说明（重要）
- 这里实现的是「流式异或 + HMAC 校验」的轻量方案，只保证
  「数据库单独泄露时密码不是明文」，不是密码学意义上的强加密。
- 密钥落在 data/.secret（自动生成、不入库、不进 Git、与数据库同生命周期）。
- 正式生产环境请改用 KMS / cryptography 库，或干脆不做密码可逆存储。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from .config import SECRET_PATH

_KEY: bytes | None = None
_NONCE_LEN = 12
_MAC_LEN = 16


def secret_key() -> bytes:
    """读取（必要时生成）密钥文件。整进程只加载一次。"""
    global _KEY
    if _KEY is None:
        try:
            raw = SECRET_PATH.read_bytes().strip()
        except Exception:  # noqa: BLE001  文件不存在或不可读
            raw = b""
        if len(raw) < 32:
            raw = secrets.token_bytes(48)
            SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
            try:
                SECRET_PATH.write_bytes(raw)
            except Exception:  # noqa: BLE001  只读文件系统时退化为进程内密钥
                pass
        _KEY = raw
    return _KEY


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """SHA256 计数器模式生成密钥流。"""
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(out[:length])


def _xor(data: bytes, stream: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, stream))


def encrypt(plain: str) -> str:
    """把明文加密成可安全放进单列的文本；失败时返回空串。"""
    try:
        text = (plain or "").encode("utf-8")
        key = secret_key()
        nonce = secrets.token_bytes(_NONCE_LEN)
        body = _xor(text, _keystream(key, nonce, len(text)))
        mac = hmac.new(key, nonce + body, hashlib.sha256).digest()[:_MAC_LEN]
        return base64.urlsafe_b64encode(nonce + mac + body).decode("ascii")
    except Exception:  # noqa: BLE001
        return ""


def decrypt(token: str) -> str:
    """还原 encrypt() 的结果；校验失败或格式不对时返回空串。"""
    if not token:
        return ""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        if len(raw) < _NONCE_LEN + _MAC_LEN:
            return ""
        nonce = raw[:_NONCE_LEN]
        mac = raw[_NONCE_LEN:_NONCE_LEN + _MAC_LEN]
        body = raw[_NONCE_LEN + _MAC_LEN:]
        key = secret_key()
        expected = hmac.new(key, nonce + body, hashlib.sha256).digest()[:_MAC_LEN]
        if not hmac.compare_digest(mac, expected):
            return ""
        return _xor(body, _keystream(key, nonce, len(body))).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


def sign(message: str) -> str:
    """用密钥对任意消息做 HMAC-SHA256 签名（十六进制）。"""
    return hmac.new(secret_key(), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(message: str, signature: str) -> bool:
    return hmac.compare_digest(sign(message), signature or "")
