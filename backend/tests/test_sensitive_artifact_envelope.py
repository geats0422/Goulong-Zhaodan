from __future__ import annotations

import pytest

from app.core import config
from app.core.data_encryption import decrypt_sensitive_artifact, encrypt_sensitive_artifact


@pytest.fixture(scope="session")
def _ensure_schema():
    """敏感 envelope 单元测试不访问数据库。"""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """覆盖集成测试目录的数据库清理 fixture。"""


def test_sensitive_artifact_envelope_encrypts_and_round_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    plaintext = "# 机密 Markdown\n\n不得出现在存储密文中。".encode()
    monkeypatch.setattr(config.settings, "environment", "development")
    monkeypatch.setattr(config.settings, "data_encryption_key", "artifact-test-key")

    envelope = encrypt_sensitive_artifact(plaintext)

    assert plaintext not in envelope
    assert decrypt_sensitive_artifact(envelope) == plaintext


def test_sensitive_artifact_rejects_wrong_key_and_corrupt_ciphertext(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "environment", "development")
    monkeypatch.setattr(config.settings, "data_encryption_key", "first-key")
    envelope = encrypt_sensitive_artifact(b"sensitive report")

    monkeypatch.setattr(config.settings, "data_encryption_key", "wrong-key")
    with pytest.raises(ValueError, match="敏感产物解密失败"):
        decrypt_sensitive_artifact(envelope)
    with pytest.raises(ValueError, match="敏感产物解密失败"):
        decrypt_sensitive_artifact(envelope[:-1] + b"x")


def test_development_without_key_uses_explicit_plaintext_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "environment", "development")
    monkeypatch.setattr(config.settings, "data_encryption_key", "")

    envelope = encrypt_sensitive_artifact(b"local only")

    assert envelope != b"local only"
    assert decrypt_sensitive_artifact(envelope) == b"local only"


def test_production_without_key_rejects_sensitive_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "environment", "production")
    monkeypatch.setattr(config.settings, "data_encryption_key", "")

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY"):
        encrypt_sensitive_artifact(b"must fail closed")
    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY"):
        decrypt_sensitive_artifact(b"GZSA1:F:anything")
