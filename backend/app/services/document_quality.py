"""文档文本质量与 PDF 文本层的纯函数判定。"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol, Sequence

_IMAGE_PLACEHOLDER_PATTERN = re.compile(
    r"!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>|\[(?:image|图片)[^\]]*\]",
    re.IGNORECASE,
)
_GARBLED_PATTERNS = (
    re.compile(r"锟斤拷|烫烫烫|屯屯屯"),
    re.compile(r"ï¿½|â€|Ã.|Â."),
)


class PdfDocumentKind(StrEnum):
    """按有效文本页比例划分的 PDF 类型。"""

    TEXT = "text"
    SCANNED = "scanned"
    MIXED = "mixed"


class QualitySettings(Protocol):
    document_min_non_whitespace_chars: int
    document_min_printable_ratio: float
    document_max_replacement_character_ratio: float
    document_max_garbled_character_ratio: float
    document_max_image_placeholder_ratio: float
    document_min_valid_pdf_page_chars: int


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    """文本质量阈值；调用方可注入实例进行集中调优。"""

    min_non_whitespace_length: int = 50
    min_printable_ratio: float = 0.95
    max_replacement_character_ratio: float = 0.01
    max_garbled_character_ratio: float = 0.05
    max_image_placeholder_ratio: float = 0.4
    min_valid_pdf_page_length: int = 20


@dataclass(frozen=True, slots=True)
class TextQuality:
    non_whitespace_length: int
    printable_ratio: float
    replacement_character_ratio: float
    garbled_character_ratio: float
    image_placeholder_ratio: float
    is_acceptable: bool


@dataclass(frozen=True, slots=True)
class PdfTextLayerQuality:
    total_pages: int
    valid_text_pages: int
    valid_text_page_ratio: float
    average_text_length_per_page: float
    document_kind: PdfDocumentKind


DEFAULT_QUALITY_THRESHOLDS = QualityThresholds()


def quality_thresholds_from_settings(app_settings: QualitySettings) -> QualityThresholds:
    """从配置对象构造阈值，避免质量模块反向导入全局配置。"""
    return QualityThresholds(
        min_non_whitespace_length=app_settings.document_min_non_whitespace_chars,
        min_printable_ratio=app_settings.document_min_printable_ratio,
        max_replacement_character_ratio=app_settings.document_max_replacement_character_ratio,
        max_garbled_character_ratio=app_settings.document_max_garbled_character_ratio,
        max_image_placeholder_ratio=app_settings.document_max_image_placeholder_ratio,
        min_valid_pdf_page_length=app_settings.document_min_valid_pdf_page_chars,
    )


def assess_text_quality(
    text: str,
    thresholds: QualityThresholds = DEFAULT_QUALITY_THRESHOLDS,
) -> TextQuality:
    """计算 Markdown/文本质量指标，不修改输入或外部状态。"""
    total_length = len(text)
    non_whitespace_length = sum(not character.isspace() for character in text)
    denominator = non_whitespace_length or 1
    printable_characters = sum(character.isprintable() or character.isspace() for character in text)
    printable_ratio = printable_characters / total_length if total_length else 0.0
    replacement_character_ratio = text.count("\ufffd") / denominator
    garbled_length = sum(
        len(match.group(0))
        for pattern in _GARBLED_PATTERNS
        for match in pattern.finditer(text)
    )
    garbled_character_ratio = min(garbled_length / denominator, 1.0)
    placeholder_length = sum(len(match.group(0)) for match in _IMAGE_PLACEHOLDER_PATTERN.finditer(text))
    image_placeholder_ratio = min(placeholder_length / denominator, 1.0)

    is_acceptable = (
        non_whitespace_length >= thresholds.min_non_whitespace_length
        and printable_ratio >= thresholds.min_printable_ratio
        and replacement_character_ratio <= thresholds.max_replacement_character_ratio
        and garbled_character_ratio <= thresholds.max_garbled_character_ratio
        and image_placeholder_ratio <= thresholds.max_image_placeholder_ratio
    )
    return TextQuality(
        non_whitespace_length=non_whitespace_length,
        printable_ratio=printable_ratio,
        replacement_character_ratio=replacement_character_ratio,
        garbled_character_ratio=garbled_character_ratio,
        image_placeholder_ratio=image_placeholder_ratio,
        is_acceptable=is_acceptable,
    )


def assess_pdf_text_layer(
    page_texts: Sequence[str],
    thresholds: QualityThresholds = DEFAULT_QUALITY_THRESHOLDS,
) -> PdfTextLayerQuality:
    """根据逐页已提取文本判定 PDF 是文本型、扫描型还是混合型。"""
    if isinstance(page_texts, (str, bytes)):
        raise TypeError("PDF pages 必须是页文本序列，不能是单个 str/bytes")

    page_thresholds = replace(
        thresholds,
        min_non_whitespace_length=thresholds.min_valid_pdf_page_length,
    )
    page_lengths = [sum(not character.isspace() for character in text) for text in page_texts]
    valid_text_pages = sum(
        assess_text_quality(text, page_thresholds).is_acceptable
        for text in page_texts
    )
    total_pages = len(page_texts)
    valid_text_page_ratio = valid_text_pages / total_pages if total_pages else 0.0
    average_text_length_per_page = sum(page_lengths) / total_pages if total_pages else 0.0

    if total_pages > 0 and valid_text_pages == total_pages:
        document_kind = PdfDocumentKind.TEXT
    elif valid_text_pages == 0:
        document_kind = PdfDocumentKind.SCANNED
    else:
        document_kind = PdfDocumentKind.MIXED

    return PdfTextLayerQuality(
        total_pages=total_pages,
        valid_text_pages=valid_text_pages,
        valid_text_page_ratio=valid_text_page_ratio,
        average_text_length_per_page=average_text_length_per_page,
        document_kind=document_kind,
    )
