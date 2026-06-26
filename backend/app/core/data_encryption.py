from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet

from app.core import config

_logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet | None:
    key = config.settings.data_encryption_key
    if not key:
        return None
    derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
    return Fernet(derived)


def encrypt_text(plain: str) -> str:
    if not plain:
        return plain
    f = _get_fernet()
    if f is None:
        _logger.warning("DATA_ENCRYPTION_KEY 未配置，数据未加密存储")
        return plain
    return f.encrypt(plain.encode()).decode()


def decrypt_text(encrypted: str) -> str:
    if not encrypted:
        return encrypted
    f = _get_fernet()
    if f is None:
        return encrypted
    try:
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        _logger.warning("数据解密失败，可能因密钥变更")
        return "[解密失败]"


def safe_decrypt_text(value: str) -> str:
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value
