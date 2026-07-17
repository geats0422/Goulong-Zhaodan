"""根据文件类型与 PDF 文本层分类生成解析决策。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence

from app.core.config import settings
from app.services.document_quality import (
    PdfDocumentKind,
    QualityThresholds,
    assess_pdf_text_layer,
    quality_thresholds_from_settings,
)


class ParserEngine(StrEnum):
    DIRECT_TEXT = "text"
    MARKITDOWN = "markitdown"
    MINERU = "mineru"


class ConversionFailureAction(StrEnum):
    FAIL = "fail"
    CONVERT_TO_PDF = "convert_to_pdf"


class UnsupportedDocumentTypeError(ValueError):
    """文件类型不在统一解析服务支持范围内。"""


@dataclass(frozen=True, slots=True)
class DocumentRouteDecision:
    primary_engine: ParserEngine
    fallback_engine: ParserEngine | None = None
    requires_quality_gate: bool = False
    conversion_failure_action: ConversionFailureAction = ConversionFailureAction.FAIL
    failure_message: str = ""


_DIRECT_TEXT_SUFFIXES = frozenset({".txt", ".md"})
_WORD_SUFFIXES = frozenset({".doc", ".docx"})
_MARKITDOWN_ONLY_SUFFIXES = frozenset({".pptx", ".xlsx"})


def route_document(
    suffix: str,
    pdf_document_kind: PdfDocumentKind | None = None,
    *,
    job_type: str = "knowledge",
    pdf_page_texts: Sequence[str] | None = None,
    thresholds: QualityThresholds | None = None,
) -> DocumentRouteDecision:
    """返回不可变解析决策；PDF 必须先完成文本层分类。"""
    normalized_suffix = _normalize_suffix(suffix)
    if normalized_suffix in _DIRECT_TEXT_SUFFIXES:
        return DocumentRouteDecision(primary_engine=ParserEngine.DIRECT_TEXT)
    if normalized_suffix in _WORD_SUFFIXES:
        if job_type == "inspection":
            return DocumentRouteDecision(primary_engine=ParserEngine.MARKITDOWN)
        return _markitdown_with_mineru_fallback()
    if normalized_suffix == ".pdf":
        if pdf_document_kind is None and pdf_page_texts is not None:
            effective_thresholds = thresholds or quality_thresholds_from_settings(settings)
            pdf_document_kind = assess_pdf_text_layer(pdf_page_texts, effective_thresholds).document_kind
        if pdf_document_kind is None:
            raise ValueError("路由 PDF 前必须提供 PDF 文本层分类")
        if job_type == "inspection":
            return DocumentRouteDecision(primary_engine=ParserEngine.MARKITDOWN)
        if pdf_document_kind is PdfDocumentKind.TEXT:
            return _markitdown_with_mineru_fallback()
        return DocumentRouteDecision(primary_engine=ParserEngine.MINERU)
    if normalized_suffix in _MARKITDOWN_ONLY_SUFFIXES:
        return DocumentRouteDecision(
            primary_engine=ParserEngine.MARKITDOWN,
            conversion_failure_action=ConversionFailureAction.CONVERT_TO_PDF,
            failure_message="本地解析失败，请将文件转换为 PDF 后重新上传。",
        )
    raise UnsupportedDocumentTypeError(f"不支持的文档类型：{normalized_suffix}")


def select_engine_after_quality_gate(
    decision: DocumentRouteDecision,
    *,
    is_acceptable: bool,
) -> ParserEngine:
    """根据 MarkItDown 质量门禁选择最终引擎。"""
    if not decision.requires_quality_gate or is_acceptable:
        return decision.primary_engine
    if decision.fallback_engine is None:
        raise ValueError("低质量解析结果没有可用的后备引擎")
    return decision.fallback_engine


def _markitdown_with_mineru_fallback() -> DocumentRouteDecision:
    return DocumentRouteDecision(
        primary_engine=ParserEngine.MARKITDOWN,
        fallback_engine=ParserEngine.MINERU,
        requires_quality_gate=True,
    )


def _normalize_suffix(suffix: str) -> str:
    normalized = suffix.strip().lower()
    if not normalized:
        raise UnsupportedDocumentTypeError("不支持空文件类型")
    return normalized if normalized.startswith(".") else f".{normalized}"
