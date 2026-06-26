from __future__ import annotations

import pytest

from app.core.config import Settings, assert_production_security


def test_development_env_skips_check():
    s = Settings(environment="development")
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        assert_production_security()
    finally:
        config.settings = original


def test_production_env_default_jwt_key_raises():
    s = Settings(
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
        environment="production",
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
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-encryption-secret",
        api_key="real-api-key",
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
        environment="production",
        jwt_secret_key="real-jwt-secret",
        api_key_encryption_secret="real-encryption-secret",
        api_key="real-api-key",
        data_encryption_key="real-data-key",
        model_api_key="sk-real-key",
    )
    from app.core import config

    original = config.settings
    config.settings = s
    try:
        assert_production_security()
    finally:
        config.settings = original
