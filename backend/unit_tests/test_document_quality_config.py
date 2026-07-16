from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.document_quality import quality_thresholds_from_settings


DOCUMENT_ENVIRONMENT = {
    "DOCUMENT_MIN_NON_WHITESPACE_CHARS": "80",
    "DOCUMENT_MIN_PRINTABLE_RATIO": "0.91",
    "DOCUMENT_MAX_REPLACEMENT_CHARACTER_RATIO": "0.02",
    "DOCUMENT_MAX_GARBLED_CHARACTER_RATIO": "0.06",
    "DOCUMENT_MAX_IMAGE_PLACEHOLDER_RATIO": "0.35",
    "DOCUMENT_MIN_VALID_PDF_PAGE_CHARS": "30",
    "DOCUMENT_MAX_PARSE_BYTES": "1048576",
}


def test_quality_thresholds_are_loaded_from_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in DOCUMENT_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)

    app_settings = Settings(_env_file=None)
    thresholds = quality_thresholds_from_settings(app_settings)

    assert thresholds.min_non_whitespace_length == 80
    assert thresholds.min_printable_ratio == pytest.approx(0.91)
    assert thresholds.max_replacement_character_ratio == pytest.approx(0.02)
    assert thresholds.max_garbled_character_ratio == pytest.approx(0.06)
    assert thresholds.max_image_placeholder_ratio == pytest.approx(0.35)
    assert thresholds.min_valid_pdf_page_length == 30
    assert app_settings.document_max_parse_bytes == 1048576


@pytest.mark.parametrize(
    ("environment_name", "invalid_value"),
    [
        ("DOCUMENT_MIN_NON_WHITESPACE_CHARS", "0"),
        ("DOCUMENT_MIN_PRINTABLE_RATIO", "1.01"),
        ("DOCUMENT_MAX_REPLACEMENT_CHARACTER_RATIO", "-0.01"),
        ("DOCUMENT_MAX_GARBLED_CHARACTER_RATIO", "1.01"),
        ("DOCUMENT_MAX_IMAGE_PLACEHOLDER_RATIO", "-0.01"),
        ("DOCUMENT_MIN_VALID_PDF_PAGE_CHARS", "0"),
        ("DOCUMENT_MAX_PARSE_BYTES", "0"),
    ],
)
def test_quality_threshold_environment_values_have_safe_ranges(
    monkeypatch: pytest.MonkeyPatch,
    environment_name: str,
    invalid_value: str,
) -> None:
    monkeypatch.setenv(environment_name, invalid_value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("example_name", [".env.example", "env.example"])
def test_environment_examples_are_read_back_with_matching_quality_defaults(
    monkeypatch: pytest.MonkeyPatch,
    example_name: str,
) -> None:
    for environment_name in DOCUMENT_ENVIRONMENT:
        monkeypatch.delenv(environment_name, raising=False)

    backend_dir = Path(__file__).resolve().parents[1]
    app_settings = Settings(_env_file=backend_dir / example_name)
    thresholds = quality_thresholds_from_settings(app_settings)

    assert thresholds.min_non_whitespace_length == 50
    assert thresholds.min_printable_ratio == pytest.approx(0.95)
    assert thresholds.max_replacement_character_ratio == pytest.approx(0.01)
    assert thresholds.max_garbled_character_ratio == pytest.approx(0.05)
    assert thresholds.max_image_placeholder_ratio == pytest.approx(0.4)
    assert thresholds.min_valid_pdf_page_length == 20
    assert app_settings.document_max_parse_bytes == 50 * 1024 * 1024
