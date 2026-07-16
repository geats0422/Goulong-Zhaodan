from __future__ import annotations

import pytest

from app.core import config
from app.core.config import Settings, assert_production_security
from app.core.data_encryption import encrypt_sensitive_artifact


def test_document_artifact_retention_defaults_to_thirty_days() -> None:
    settings = Settings(_env_file=None)

    assert settings.document_artifact_retention_days == 30


def test_production_rejects_whitespace_data_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.settings, "environment", "production")
    monkeypatch.setattr(config.settings, "data_encryption_key", "   ")

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY"):
        encrypt_sensitive_artifact(b"sensitive")


def test_production_startup_rejects_whitespace_data_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    production = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-api-key-secret",
        data_encryption_key="   ",
        model_api_key="sk-real-key",
        model_base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-pro",
        mineru_api_token="mineru-token",
        mineru_trusted_hosts="objects.example",
        database_url="postgresql+asyncpg://postgres:password@localhost:5432/goulong",
    )
    monkeypatch.setattr(config, "settings", production)

    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY"):
        assert_production_security()
