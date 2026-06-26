from __future__ import annotations

import os

from app.core.config import Settings

_test_settings = Settings(data_encryption_key="test-encryption-key-for-unit-tests", environment="development")
os.environ["DATA_ENCRYPTION_KEY"] = "test-encryption-key-for-unit-tests"
os.environ["ENVIRONMENT"] = "development"

from app.core import config as _config  # noqa: E402
_config.settings = _test_settings

from app.core.data_encryption import decrypt_text, encrypt_text, safe_decrypt_text  # noqa: E402


def test_encrypt_decrypt_roundtrip() -> None:
    plain = "这是一段需要加密的合同内容"
    encrypted = encrypt_text(plain)
    decrypted = decrypt_text(encrypted)
    assert decrypted == plain


def test_encrypted_not_equal_plaintext() -> None:
    plain = "敏感信息123456"
    encrypted = encrypt_text(plain)
    assert encrypted != plain


def test_different_plaintexts_different_ciphertexts() -> None:
    plain_a = "合同甲方信息"
    plain_b = "合同乙方信息"
    assert encrypt_text(plain_a) != encrypt_text(plain_b)


def test_empty_string_passthrough() -> None:
    assert encrypt_text("") == ""
    assert decrypt_text("") == ""
    assert safe_decrypt_text("") == ""


def test_safe_decrypt_plaintext_fallback() -> None:
    plain = "这段文字从未被加密"
    assert safe_decrypt_text(plain) == plain


def test_safe_decrypt_encrypted_success() -> None:
    plain = "加密后再解密"
    encrypted = encrypt_text(plain)
    assert safe_decrypt_text(encrypted) == plain


def test_dev_env_no_key_ok() -> None:
    from app.core.config import Settings

    original = os.environ.pop("DATA_ENCRYPTION_KEY", None)
    try:
        dev_settings = Settings(
            environment="development",
            data_encryption_key="",
        )
        key = dev_settings.data_encryption_key
        assert key == ""
    finally:
        if original is not None:
            os.environ["DATA_ENCRYPTION_KEY"] = original


def test_encrypt_chinese_text() -> None:
    plain = "甲方：北京科技有限公司，乙方：上海贸易集团，合同金额：壹佰万元整"
    encrypted = encrypt_text(plain)
    decrypted = decrypt_text(encrypted)
    assert decrypted == plain
    assert encrypted != plain


def test_encrypt_large_text() -> None:
    plain = "合同条款内容。" * 200
    assert len(plain) > 1000
    encrypted = encrypt_text(plain)
    decrypted = decrypt_text(encrypted)
    assert decrypted == plain
