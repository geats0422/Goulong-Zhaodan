"""API Key 生成、哈希与加密工具"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet

from app.core.config import settings

PREFIX = "glzd_live_"


def generate_api_key() -> str:
    return PREFIX + secrets.token_hex(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key_hash(plain_key: str, hashed: str) -> bool:
    computed = hashlib.sha256(plain_key.encode()).hexdigest()
    return hmac.compare_digest(computed, hashed)


def get_key_prefix(key: str) -> str:
    return key[: len(PREFIX) + 8]


def _get_encryption_secret() -> str:
    return settings.api_key_encryption_secret


def _make_fernet() -> Fernet:
    secret = _get_encryption_secret()
    if not secret:
        raise ValueError("api_key_encryption_secret 未配置，无法加解密 API Key")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_api_key(plain_key: str) -> str:
    return _make_fernet().encrypt(plain_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    return _make_fernet().decrypt(encrypted.encode()).decode()
