from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core import config

_logger = logging.getLogger(__name__)
_SENSITIVE_FERNET_MAGIC = b"GZSA1:F:"
_SENSITIVE_PLAINTEXT_MAGIC = b"GZSA1:P:"


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


def encrypt_sensitive_artifact(plaintext: bytes) -> bytes:
    """生成可版本识别的敏感产物 envelope；生产环境缺少密钥时拒绝写入。"""
    if config.settings.environment == "production" and not config.settings.data_encryption_key.strip():
        raise RuntimeError("生产环境必须配置 DATA_ENCRYPTION_KEY 才能写入敏感产物")
    fernet = _get_fernet()
    if fernet is not None:
        return _SENSITIVE_FERNET_MAGIC + fernet.encrypt(plaintext)
    if config.settings.environment == "production":
        raise RuntimeError("生产环境必须配置 DATA_ENCRYPTION_KEY 才能写入敏感产物")
    return _SENSITIVE_PLAINTEXT_MAGIC + plaintext


def decrypt_sensitive_artifact(envelope: bytes, *, allow_legacy_plaintext: bool = False) -> bytes:
    """严格解开敏感产物；密钥或密文错误绝不回退为正文。"""
    if envelope.startswith(_SENSITIVE_FERNET_MAGIC):
        if config.settings.environment == "production" and not config.settings.data_encryption_key.strip():
            raise RuntimeError("生产环境必须配置 DATA_ENCRYPTION_KEY 才能读取敏感产物")
        fernet = _get_fernet()
        if fernet is None:
            if config.settings.environment == "production":
                raise RuntimeError("生产环境必须配置 DATA_ENCRYPTION_KEY 才能读取敏感产物")
            raise ValueError("敏感产物解密失败")
        try:
            return fernet.decrypt(envelope[len(_SENSITIVE_FERNET_MAGIC) :])
        except InvalidToken:
            raise ValueError("敏感产物解密失败") from None
    if envelope.startswith(_SENSITIVE_PLAINTEXT_MAGIC):
        if config.settings.environment == "production":
            raise ValueError("生产环境拒绝明文敏感产物")
        return envelope[len(_SENSITIVE_PLAINTEXT_MAGIC) :]
    if allow_legacy_plaintext and config.settings.environment != "production":
        return envelope
    raise ValueError("敏感产物 envelope 无效")
