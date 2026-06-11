from __future__ import annotations

import base64
import hashlib
import logging
import secrets

from cryptography.fernet import Fernet

from core.config import settings

_logger = logging.getLogger(__name__)
_dev_key: str | None = None


def _get_dev_key() -> str:
    global _dev_key
    if _dev_key is None:
        _dev_key = secrets.token_hex(32)
        _logger.warning("DATA_ENCRYPTION_KEY 未配置，使用随机临时密钥（服务重启后数据将无法解密）")
    return _dev_key


def _get_fernet() -> Fernet:
    key = settings.data_encryption_key
    if not key:
        if settings.environment == "production":
            raise ValueError("DATA_ENCRYPTION_KEY 未配置")
        key = _get_dev_key()
    derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
    return Fernet(derived)


def encrypt_text(plain: str) -> str:
    if not plain:
        return plain
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_text(encrypted: str) -> str:
    if not encrypted:
        return encrypted
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


def safe_decrypt_text(value: str) -> str:
    if not value:
        return value
    try:
        decrypted = _get_fernet().decrypt(value.encode()).decode()
        return decrypted
    except Exception:
        return value
