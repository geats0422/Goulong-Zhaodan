import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.model_config import (
    MODEL_CATALOG,
    configure_openai_environment,
    normalize_model_name,
    validate_official_deepseek_configuration,
)


def test_default_model_configuration_uses_official_deepseek_api() -> None:
    assert Settings.model_fields["model_base_url"].default == "https://api.deepseek.com/v1"
    assert Settings.model_fields["model_name"].default == "deepseek-v4-pro"


def test_model_catalog_uses_official_unprefixed_names() -> None:
    assert {item["model_name"] for item in MODEL_CATALOG} == {
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    }


def test_legacy_gateway_model_name_is_normalized() -> None:
    assert normalize_model_name("deepseek-ai/deepseek-v4-pro") == "deepseek-v4-pro"
    assert normalize_model_name("deepseek-ai/deepseek-v4-flash") == "deepseek-v4-flash"
    assert normalize_model_name("deepseek-v4-pro") == "deepseek-v4-pro"
    assert normalize_model_name(None) is None


def test_model_environment_overrides_stale_gateway_values() -> None:
    environ = {
        "OPENAI_API_KEY": "stale-key",
        "OPENAI_API_BASE": "https://old-gateway.example/v1",
    }

    configure_openai_environment(
        environ,
        api_key="official-key",
        base_url="https://api.deepseek.com/v1",
    )

    assert environ["OPENAI_API_KEY"] == "official-key"
    assert environ["OPENAI_API_BASE"] == "https://api.deepseek.com/v1"


def test_production_configuration_rejects_third_party_gateway() -> None:
    with pytest.raises(RuntimeError, match="DeepSeek 官方 API"):
        validate_official_deepseek_configuration(
            "https://third-party.example/v1", "deepseek-ai/deepseek-v4-pro"
        )

    validate_official_deepseek_configuration(
        "https://api.deepseek.com/v1", "deepseek-v4-pro"
    )
