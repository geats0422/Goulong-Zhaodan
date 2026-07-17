from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.document_quality import PdfDocumentKind, QualityThresholds, assess_pdf_text_layer
from app.services import document_router
from app.services.document_router import (
    ConversionFailureAction,
    ParserEngine,
    UnsupportedDocumentTypeError,
    route_document,
    select_engine_after_quality_gate,
)


@pytest.mark.parametrize("suffix", [".txt", "md", ".MD"])
def test_plain_text_files_are_read_directly(suffix: str) -> None:
    decision = route_document(suffix)

    assert decision.primary_engine is ParserEngine.DIRECT_TEXT
    assert decision.fallback_engine is None
    assert decision.requires_quality_gate is False


@pytest.mark.parametrize("suffix", [".doc", ".docx"])
def test_knowledge_word_uses_markitdown_with_mineru_quality_fallback(suffix: str) -> None:
    decision = route_document(suffix, job_type="knowledge")

    assert decision.primary_engine is ParserEngine.MARKITDOWN
    assert decision.fallback_engine is ParserEngine.MINERU
    assert decision.requires_quality_gate is True


def test_knowledge_low_quality_word_or_text_pdf_falls_back_to_mineru() -> None:
    word_decision = route_document(".docx", job_type="knowledge")
    pdf_decision = route_document(".pdf", PdfDocumentKind.TEXT, job_type="knowledge")

    assert select_engine_after_quality_gate(word_decision, is_acceptable=False) is ParserEngine.MINERU
    assert select_engine_after_quality_gate(pdf_decision, is_acceptable=False) is ParserEngine.MINERU
    assert select_engine_after_quality_gate(pdf_decision, is_acceptable=True) is ParserEngine.MARKITDOWN


def test_inspection_word_and_text_pdf_never_fall_back_to_mineru() -> None:
    word_decision = route_document(".docx", job_type="inspection")
    pdf_decision = route_document(".pdf", PdfDocumentKind.TEXT, job_type="inspection")

    assert word_decision.primary_engine is ParserEngine.MARKITDOWN
    assert word_decision.fallback_engine is None
    assert word_decision.requires_quality_gate is False
    assert select_engine_after_quality_gate(word_decision, is_acceptable=False) is ParserEngine.MARKITDOWN
    assert pdf_decision.primary_engine is ParserEngine.MARKITDOWN
    assert pdf_decision.fallback_engine is None
    assert pdf_decision.requires_quality_gate is False
    assert select_engine_after_quality_gate(pdf_decision, is_acceptable=False) is ParserEngine.MARKITDOWN


def test_knowledge_text_pdf_uses_markitdown_with_a_second_quality_gate() -> None:
    decision = route_document(".pdf", PdfDocumentKind.TEXT, job_type="knowledge")

    assert decision.primary_engine is ParserEngine.MARKITDOWN
    assert decision.fallback_engine is ParserEngine.MINERU
    assert decision.requires_quality_gate is True


@pytest.mark.parametrize("kind", [PdfDocumentKind.SCANNED, PdfDocumentKind.MIXED])
def test_knowledge_scanned_and_mixed_pdf_go_directly_to_mineru(kind: PdfDocumentKind) -> None:
    decision = route_document("pdf", kind, job_type="knowledge")

    assert decision.primary_engine is ParserEngine.MINERU
    assert decision.fallback_engine is None
    assert decision.requires_quality_gate is False


@pytest.mark.parametrize("kind", [PdfDocumentKind.SCANNED, PdfDocumentKind.MIXED])
def test_inspection_scanned_and_mixed_pdf_use_local_parser_without_mineru(kind: PdfDocumentKind) -> None:
    decision = route_document("pdf", kind, job_type="inspection")

    assert decision.primary_engine is ParserEngine.MARKITDOWN
    assert decision.fallback_engine is None
    assert decision.requires_quality_gate is False


@pytest.mark.parametrize("valid_pages,total_pages", [(4, 5), (9, 10)])
def test_pdf_with_even_one_invalid_page_routes_directly_to_mineru(
    valid_pages: int,
    total_pages: int,
) -> None:
    pages = ["正常正文" * 30] * valid_pages + [""] * (total_pages - valid_pages)
    quality = assess_pdf_text_layer(pages)

    decision = route_document(".pdf", quality.document_kind)

    assert quality.document_kind is PdfDocumentKind.MIXED
    assert decision.primary_engine is ParserEngine.MINERU


def test_pdf_requires_text_layer_classification() -> None:
    with pytest.raises(ValueError, match="PDF 文本层分类"):
        route_document(".pdf")


def test_pdf_page_routing_uses_current_settings_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    configured_settings = SimpleNamespace(
        document_min_non_whitespace_chars=50,
        document_min_printable_ratio=0.95,
        document_max_replacement_character_ratio=0.01,
        document_max_garbled_character_ratio=0.05,
        document_max_image_placeholder_ratio=0.4,
        document_min_valid_pdf_page_chars=5,
    )
    monkeypatch.setattr(document_router, "settings", configured_settings)

    decision = route_document(".pdf", pdf_page_texts=["有效正文" * 2])

    assert decision.primary_engine is ParserEngine.MARKITDOWN


def test_pdf_page_routing_allows_threshold_injection() -> None:
    thresholds = QualityThresholds(min_valid_pdf_page_length=100)

    decision = route_document(
        ".pdf",
        pdf_page_texts=["有效正文" * 2],
        thresholds=thresholds,
    )

    assert decision.primary_engine is ParserEngine.MINERU


@pytest.mark.parametrize("suffix", [".pptx", ".xlsx"])
def test_presentation_and_spreadsheet_only_use_markitdown(suffix: str) -> None:
    decision = route_document(suffix)

    assert decision.primary_engine is ParserEngine.MARKITDOWN
    assert decision.fallback_engine is None
    assert decision.requires_quality_gate is False
    assert decision.conversion_failure_action is ConversionFailureAction.CONVERT_TO_PDF
    assert "PDF" in decision.failure_message


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".jpeg", ".webp", ".gif"])
def test_images_are_not_supported(suffix: str) -> None:
    with pytest.raises(UnsupportedDocumentTypeError, match="不支持"):
        route_document(suffix)


def test_unknown_document_type_is_rejected() -> None:
    with pytest.raises(UnsupportedDocumentTypeError, match="不支持"):
        route_document(".rtf")
