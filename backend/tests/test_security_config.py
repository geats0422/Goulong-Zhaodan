from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings, assert_production_security


def test_environment_rejects_unknown_value():
    """未知 ENVIRONMENT 必须启动失败，禁止静默按本地模式运行。"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, environment="staging")
    message = str(exc_info.value)
    assert "ENVIRONMENT" in message
    assert "local" in message and "production" in message


def test_environment_accepts_local():
    """local 是推荐的本地调试值，必须被接受。"""
    s = Settings(_env_file=None, environment="local")
    assert s.environment == "local"


def test_environment_accepts_production():
    """production 必须被接受。"""
    s = Settings(_env_file=None, environment="production")
    assert s.environment == "production"


def test_environment_development_emits_migration_warning(caplog):
    """development 兼容旧配置，必须按 local 处理并输出迁移提示警告。"""
    with caplog.at_level(logging.WARNING, logger="app.core.config"):
        s = Settings(_env_file=None, environment="development")
    assert s.environment == "development"
    assert any(
        "local" in rec.message and "迁移" in rec.message
        for rec in caplog.records
        if rec.name == "app.core.config"
    ), "development 必须输出迁移到 local 的提示警告"


def test_development_env_skips_check():
    s = Settings(_env_file=None, environment="development")
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        assert_production_security()
    finally:
        config.settings = original


def test_production_env_default_jwt_key_raises():
    s = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="goulong-jwt-dev-secret-change-in-production",
        model_api_key="sk-real-key",
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        with pytest.raises(RuntimeError, match="jwt_secret_key"):
            assert_production_security()
    finally:
        config.settings = original


def test_production_env_default_api_key_encryption_raises():
    s = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="dev-encryption-secret-change-in-production",
        model_api_key="sk-real-key",
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        with pytest.raises(RuntimeError, match="api_key_encryption_secret"):
            assert_production_security()
    finally:
        config.settings = original


def test_production_env_no_model_api_key_raises():
    s = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-encryption-secret",
        data_encryption_key="real-data-key",
        model_api_key="",
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
            assert_production_security()
    finally:
        config.settings = original


def test_production_env_all_configured_passes():
    s = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-encryption-secret",
        data_encryption_key="real-data-key",
        model_api_key="sk-real-key",
        model_base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-pro",
        mineru_api_token="mineru-test-token",
        mineru_trusted_hosts="objects.example,.trusted-storage.example",
        database_url="postgresql+asyncpg://postgres:test-password@localhost:5432/goulong",
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        assert_production_security()
    finally:
        config.settings = original


@pytest.mark.parametrize("fixed_code", ["123456", " "])
def test_production_env_fixed_sms_code_raises(fixed_code):
    s = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-encryption-secret",
        data_encryption_key="real-data-key",
        model_api_key="sk-real-key",
        model_base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-pro",
        mineru_api_token="mineru-test-token",
        mineru_trusted_hosts="objects.example",
        database_url="postgresql+asyncpg://postgres:test-password@localhost:5432/goulong",
        sms_fixed_code=fixed_code,
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        with pytest.raises(RuntimeError, match="SMS_FIXED_CODE"):
            assert_production_security()
    finally:
        config.settings = original


def test_development_env_fixed_sms_code_skips_check():
    s = Settings(_env_file=None, environment="development", sms_fixed_code="123456")
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        assert_production_security() is None
    finally:
        config.settings = original


def test_production_oss_mode_requires_complete_oss_configuration():
    s = Settings(
        _env_file=None,
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-encryption-secret",
        data_encryption_key="real-data-key",
        model_api_key="sk-real-key",
        model_base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-pro",
        mineru_api_token="mineru-test-token",
        mineru_trusted_hosts="objects.example",
        database_url="postgresql+asyncpg://postgres:test-password@localhost:5432/goulong",
        storage_backend="oss",
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        with pytest.raises(RuntimeError, match="OSS_ACCESS_KEY_ID"):
            assert_production_security()
    finally:
        config.settings = original
