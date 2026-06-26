"""API Key 加密/hash 工具测试"""
import pytest

from app.core.api_key_crypto import (
    decrypt_api_key,
    encrypt_api_key,
    generate_api_key,
    get_key_prefix,
    hash_api_key,
    verify_api_key_hash,
)


class TestGenerateApiKey:
    def test_returns_glzd_live_prefix(self):
        key = generate_api_key()
        assert key.startswith("glzd_live_")

    def test_length_at_least_40(self):
        key = generate_api_key()
        assert len(key) >= 40

    def test_unique_on_each_call(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1 != key2


class TestHashApiKey:
    def test_deterministic(self):
        plain = "glzd_live_abc123testkey"
        assert hash_api_key(plain) == hash_api_key(plain)

    def test_different_inputs_different_hashes(self):
        h1 = hash_api_key("key_one")
        h2 = hash_api_key("key_two")
        assert h1 != h2


class TestVerifyApiKeyHash:
    def test_correct_key_passes(self):
        plain = "glzd_live_correct_key_value"
        assert verify_api_key_hash(plain, hash_api_key(plain)) is True

    def test_wrong_key_fails(self):
        real_hash = hash_api_key("real_key")
        assert verify_api_key_hash("wrong_key", real_hash) is False


class TestEncryptDecryptApiKey:
    def test_roundtrip(self):
        plain = "glzd_live_roundtrip_test_key"
        encrypted = encrypt_api_key(plain)
        assert decrypt_api_key(encrypted) == plain

    def test_encrypted_differs_from_plain(self):
        plain = "glzd_live_must_differ_key"
        assert encrypt_api_key(plain) != plain


class TestGetKeyPrefix:
    def test_extracts_prefix(self):
        key = "glzd_live_ab12cd34xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        assert get_key_prefix(key) == "glzd_live_ab12cd34"


class TestMissingEncryptionSecret:
    def test_encrypt_raises_without_secret(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.api_key_crypto._get_encryption_secret",
            lambda: "",
        )
        with pytest.raises((ValueError, RuntimeError)):
            encrypt_api_key("glzd_live_some_key")
