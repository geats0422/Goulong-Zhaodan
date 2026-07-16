from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.document_quality import (
    PdfDocumentKind,
    QualityThresholds,
    assess_pdf_text_layer,
    assess_text_quality,
)


def test_text_quality_reports_required_metrics_for_clean_text() -> None:
    text = "# 合同审查\n\n" + "本条款约定双方的权利和义务。" * 10

    result = assess_text_quality(text)

    assert result.non_whitespace_length >= 100
    assert result.printable_ratio == pytest.approx(1.0)
    assert result.replacement_character_ratio == 0
    assert result.garbled_character_ratio == 0
    assert result.image_placeholder_ratio == 0
    assert result.is_acceptable is True


def test_text_quality_rejects_short_or_unreadable_content() -> None:
    thresholds = QualityThresholds(min_non_whitespace_length=20)

    short = assess_text_quality("有效但太短", thresholds)
    garbled = assess_text_quality("有效正文" * 10 + "�锟斤拷" * 20, thresholds)

    assert short.is_acceptable is False
    assert garbled.replacement_character_ratio > 0
    assert garbled.garbled_character_ratio > 0
    assert garbled.is_acceptable is False


def test_text_quality_rejects_image_placeholder_dominated_markdown() -> None:
    text = "正文\n" + "![图片](image-001.png)\n" * 20

    result = assess_text_quality(text, QualityThresholds(min_non_whitespace_length=1))

    assert result.image_placeholder_ratio > 0.5
    assert result.is_acceptable is False


def test_text_quality_rejects_low_printable_character_ratio() -> None:
    text = "有效合同正文" * 20 + "\x00\x01\x02\x03" * 20

    result = assess_text_quality(text)

    assert result.printable_ratio < QualityThresholds().min_printable_ratio
    assert result.is_acceptable is False


@pytest.mark.parametrize(
    ("pages", "expected_kind", "expected_ratio"),
    [
        (["有效文本" * 20] * 5, PdfDocumentKind.TEXT, 1.0),
        (["", " ", "�锟斤拷"], PdfDocumentKind.SCANNED, 0.0),
        (["有效文本" * 20, "", "有效文本" * 20, ""], PdfDocumentKind.MIXED, 0.5),
    ],
)
def test_pdf_text_layer_classifies_by_valid_page_ratio(
    pages: list[str],
    expected_kind: PdfDocumentKind,
    expected_ratio: float,
) -> None:
    result = assess_pdf_text_layer(pages)

    assert result.document_kind is expected_kind
    assert result.valid_text_page_ratio == pytest.approx(expected_ratio)
    assert result.total_pages == len(pages)


def test_pdf_text_layer_does_not_count_small_garbled_layer_as_valid() -> None:
    pages = ["�锟斤拷" * 30, "正常正文" * 30, "", ""]

    result = assess_pdf_text_layer(pages)

    assert result.valid_text_pages == 1
    assert result.valid_text_page_ratio == pytest.approx(0.25)
    assert result.average_text_length_per_page > 0
    assert result.document_kind is PdfDocumentKind.MIXED


@pytest.mark.parametrize("valid_pages,total_pages", [(4, 5), (9, 10)])
def test_pdf_with_any_mix_of_valid_and_invalid_pages_is_mixed(
    valid_pages: int,
    total_pages: int,
) -> None:
    pages = ["正常正文" * 30] * valid_pages + [""] * (total_pages - valid_pages)

    result = assess_pdf_text_layer(pages)

    assert result.valid_text_page_ratio >= 0.8
    assert result.document_kind is PdfDocumentKind.MIXED


@pytest.mark.parametrize("pages", ["单个字符串", b"single bytes"])
def test_pdf_pages_rejects_single_string_or_bytes(pages: str | bytes) -> None:
    with pytest.raises(TypeError, match="页文本序列"):
        assess_pdf_text_layer(pages)  # type: ignore[arg-type]


def test_empty_pdf_is_classified_as_scanned_without_division_by_zero() -> None:
    result = assess_pdf_text_layer([])

    assert result.total_pages == 0
    assert result.valid_text_page_ratio == 0
    assert result.document_kind is PdfDocumentKind.SCANNED
