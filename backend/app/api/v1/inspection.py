"""体检台 API 路由"""
from __future__ import annotations

import logging
import tempfile
import re
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from app.core.auth import CurrentUserContext, get_current_user
from app.core.constants import validate_application_scenario
from app.core.data_encryption import decrypt_text
from app.core.database import get_db_session
from app.core.file_magic import validate_file_magic
from app.models.knowledge import InspectionRecord
from app.services.inspection_runner import (
    DOCUMENT_TYPE_LABELS,
    InspectionReportResponse,
    _inspection_records,
    create_pending_inspection_record,
    execute_inspection,
)
from app.services.markdown_converter import ConversionError, convert_to_markdown
from app.services.report_pdf import render_report_pdf

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspection", tags=["体检台"])
MAX_INSPECTION_FILE_SIZE = 20 * 1024 * 1024
INSPECTION_SESSION_TTL = timedelta(hours=1)
MAX_INSPECTION_SESSIONS = 100
MAX_INSPECTION_SESSIONS_PER_USER = 5
ALLOWED_INSPECTION_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx"}
DOCUMENT_TYPE_KEYWORDS = {
    "contract": ["合同", "协议", "甲方", "乙方", "民法典", "违约责任", "签订", "付款", "履约", "违约金", "不可抗力"],
    "bidding": ["招标", "投标", "招投标", "采购", "评标", "中标", "投标人", "投标保证金"],
}
DATA_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\(data:image/[^)]*\)", re.IGNORECASE)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)]\([^)]*\)")


# ─── 内存中的解析会话（按 user_id 读取隔离，后续可替换为 Redis） ───
_inspection_sessions: dict[str, dict[str, Any]] = {}


def _current_user_id(user: dict) -> uuid_mod.UUID:
    try:
        return user.user_id
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user") from exc


def _validate_inspection_filename(filename: str) -> None:
    dot_idx = filename.rfind(".")
    ext = filename[dot_idx:].lower() if dot_idx != -1 else ""
    if ext not in ALLOWED_INSPECTION_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")


def _document_type_score(filename: str, text: str, keywords: list[str]) -> int:
    filename_score = sum(filename.count(keyword) * 2 for keyword in keywords)
    text_score = sum(text.count(keyword) for keyword in keywords)
    return filename_score + text_score


def _detect_document_type(filename: str, text: str) -> dict[str, str]:
    """根据文件名和正文关键词识别文档类型。"""
    scores = {
        document_type: _document_type_score(filename, text, keywords)
        for document_type, keywords in DOCUMENT_TYPE_KEYWORDS.items()
    }

    if all(score == 0 for score in scores.values()):
        return {
            "document_type": "unknown",
            "document_type_label": DOCUMENT_TYPE_LABELS["unknown"],
            "confidence": "low",
        }

    document_type = max(("contract", "bidding"), key=lambda item: (scores[item], item == "bidding"))
    return {
        "document_type": document_type,
        "document_type_label": DOCUMENT_TYPE_LABELS[document_type],
        "confidence": "high",
    }


def _create_inspection_session(
    *,
    user_id: uuid_mod.UUID,
    filename: str,
    file_size: int,
    file_format: str,
    document_type: str,
    document_type_label: str,
    text: str,
    record_id: int | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """创建并保存用户隔离的文件解析会话。"""
    session_created_at = created_at or datetime.now(timezone.utc)
    _cleanup_expired_inspection_sessions(now=session_created_at)
    session_id = uuid4().hex
    session = {
        "id": session_id,
        "user_id": user_id,
        "filename": filename,
        "file_size": file_size,
        "file_format": file_format,
        "document_type": document_type,
        "document_type_label": document_type_label,
        "text": text,
        "text_preview": text[:500],
        "record_id": record_id,
        "created_at": session_created_at,
    }
    _inspection_sessions[session_id] = session
    _trim_inspection_sessions(user_id=user_id)
    return session


def _get_session_for_user(session_id: str, user_id: uuid_mod.UUID, now: datetime | None = None) -> dict[str, Any]:
    """按 session_id 与 user_id 读取解析会话，避免跨用户访问。"""
    session = _inspection_sessions.get(session_id)
    if session is None or session.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="解析会话不存在")
    if _is_inspection_session_expired(session, now or datetime.now(timezone.utc)):
        del _inspection_sessions[session_id]
        raise HTTPException(status_code=404, detail="解析会话不存在")
    return session


def _is_inspection_session_expired(session: dict[str, Any], now: datetime) -> bool:
    return now - session["created_at"] >= INSPECTION_SESSION_TTL


def _cleanup_expired_inspection_sessions(now: datetime | None = None) -> int:
    """清理已超过 TTL 的解析会话，返回清理数量。"""
    current_time = now or datetime.now(timezone.utc)
    expired_session_ids = [
        session_id
        for session_id, session in _inspection_sessions.items()
        if _is_inspection_session_expired(session, current_time)
    ]
    for session_id in expired_session_ids:
        del _inspection_sessions[session_id]
    return len(expired_session_ids)


def _trim_inspection_sessions(user_id: uuid_mod.UUID) -> None:
    """限制内存会话数量，避免认证用户反复上传造成内存压力。"""
    user_sessions = [
        session
        for session in _inspection_sessions.values()
        if session.get("user_id") == user_id
    ]
    _delete_oldest_sessions(user_sessions, max_count=MAX_INSPECTION_SESSIONS_PER_USER)
    _delete_oldest_sessions(list(_inspection_sessions.values()), max_count=MAX_INSPECTION_SESSIONS)


def _delete_oldest_sessions(sessions: list[dict[str, Any]], *, max_count: int) -> None:
    overflow = len(sessions) - max_count
    if overflow <= 0:
        return
    for session in sorted(sessions, key=lambda item: item["created_at"])[:overflow]:
        _inspection_sessions.pop(session["id"], None)


def _inspection_file_format(filename: str) -> str:
    dot_idx = filename.rfind(".")
    if dot_idx == -1:
        return ""
    return filename[dot_idx + 1 :].lower()


def _clean_inspection_markdown(text: str) -> str:
    """清理 markitdown 产物中不适合审查和预览的图片占位与噪声。"""
    cleaned = DATA_IMAGE_PATTERN.sub("", text)
    cleaned = MARKDOWN_IMAGE_PATTERN.sub(lambda match: match.group(1).strip(), cleaned)
    cleaned = re.sub(r"[图圖]片占位符", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*[图圖]\s*$\n+^\s*片\s*$\n+^\s*占\s*$\n+^\s*位\s*$\n+^\s*符\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


async def _read_inspection_upload_text(file: UploadFile) -> tuple[str, bytes, str]:
    """读取体检上传文件，并返回已消费的原始字节与解码文本。"""
    filename = file.filename or "unknown"
    _validate_inspection_filename(filename)

    try:
        content = await file.read(MAX_INSPECTION_FILE_SIZE + 1)
        if len(content) > MAX_INSPECTION_FILE_SIZE:
            raise HTTPException(status_code=413, detail="文件大小超过 20MB 限制")
        validate_file_magic(filename, content)
        text = _extract_inspection_text(filename, content)
    except HTTPException:
        raise
    except Exception as exc:
        _logger.exception("文件读取失败: %s", filename)
        raise HTTPException(status_code=400, detail="文件无法解析") from exc

    if len(text) < 10:
        raise HTTPException(status_code=400, detail="文件内容过短，无法体检")

    return filename, content, text


def _extract_inspection_text(filename: str, content: bytes) -> str:
    file_format = _inspection_file_format(filename)
    if file_format == "txt":
        try:
            return _clean_inspection_markdown(content.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="文件编码不是有效的 UTF-8 文本") from exc

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_format}") as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        return _clean_inspection_markdown(convert_to_markdown(temp_path))
    except ConversionError as exc:
        raise HTTPException(status_code=400, detail=f"无法解析文件内容: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


class InspectionCreateRequest(BaseModel):
    """创建体检请求"""

    project_id: str = "default"
    taboo_words: list[str] | None = None


class InspectionSessionInspectRequest(BaseModel):
    """会话审查请求"""

    project_id: str = "default"
    taboo_words: str = ""
    application_scenario: str | None = None


class InspectionParseFileResponse(BaseModel):
    """解析会话中的文件元信息响应"""

    name: str
    size: int
    format: str
    document_type: str
    documentType: str = ""
    document_type_label: str
    text_preview: str
    parsed_content: str


class InspectionParseResponse(BaseModel):
    """文件解析会话响应"""

    session_id: str
    file: InspectionParseFileResponse


class InspectionRecordListItem(BaseModel):
    id: int
    document_name: str
    project_id: str
    overall_risk: str
    summary: str
    issue_count: int
    document_type: str
    document_type_label: str
    created_at: str


class InspectionRecordPagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class InspectionRecordListResponse(BaseModel):
    items: list[InspectionRecordListItem]
    pagination: InspectionRecordPagination


class HistoryStatsSummary(BaseModel):
    total_docs: int
    hit_docs: int
    banned_rate: float
    quota_consumed: int


class HistoryStatsTrend(BaseModel):
    dates: list[str]
    total_docs: list[int]
    hit_docs: list[int]
    banned_rate: list[float]
    quota_consumed: list[int]


class HistoryStatsResponse(BaseModel):
    range: str
    timezone: str
    summary: HistoryStatsSummary
    trend: HistoryStatsTrend


def _build_last_n_dates(days: int) -> list[date]:
    today = date.today()
    return [today - timedelta(days=offset) for offset in reversed(range(days))]


def _safe_parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _calc_rate(hit_docs: int, total_docs: int) -> float:
    if total_docs == 0:
        return 0.0
    return round(hit_docs / total_docs, 4)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _strip_document_extension(document_name: str) -> str:
    suffix = Path(document_name).suffix
    if suffix:
        return document_name[: -len(suffix)]
    return document_name


def _aggregate_history_stats(records: list[dict[str, Any]], days: int = 7) -> HistoryStatsResponse:
    buckets = {
        d.isoformat(): {"total_docs": 0, "hit_docs": 0, "quota_consumed": 0}
        for d in _build_last_n_dates(days)
    }

    for record in records:
        created_at = _safe_parse_date(record.get("created_at"))
        if created_at is None:
            continue

        key = created_at.isoformat()
        if key not in buckets:
            continue

        buckets[key]["total_docs"] += 1
        if record.get("issues"):
            buckets[key]["hit_docs"] += 1
        buckets[key]["quota_consumed"] += _safe_int(record.get("quota_consumed", 0) or 0)

    dates = list(buckets.keys())
    total_docs_series = [buckets[d]["total_docs"] for d in dates]
    hit_docs_series = [buckets[d]["hit_docs"] for d in dates]
    quota_series = [buckets[d]["quota_consumed"] for d in dates]
    rate_series = [_calc_rate(hit, total) for hit, total in zip(hit_docs_series, total_docs_series)]

    total_docs = sum(total_docs_series)
    hit_docs = sum(hit_docs_series)
    quota_consumed = sum(quota_series)

    return HistoryStatsResponse(
        range="7d",
        timezone="Asia/Shanghai",
        summary=HistoryStatsSummary(
            total_docs=total_docs,
            hit_docs=hit_docs,
            banned_rate=_calc_rate(hit_docs, total_docs),
            quota_consumed=quota_consumed,
        ),
        trend=HistoryStatsTrend(
            dates=dates,
            total_docs=total_docs_series,
            hit_docs=hit_docs_series,
            banned_rate=rate_series,
            quota_consumed=quota_series,
        ),
    )


@router.post("/upload", response_model=InspectionReportResponse)
async def upload_and_inspect(
    file: UploadFile = File(..., description="待体检的工程文档"),
    project_id: str = Form(default="default"),
    application_scenario: str = Form(default="bidding"),
    taboo_words: str = Form(default=""),
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionReportResponse:
    """
    上传文档并执行智能体检。

    支持格式：txt、pdf、doc、docx（MVP 阶段按文本解码处理）
    """
    filename, _, text = await _read_inspection_upload_text(file)

    try:
        validate_application_scenario(application_scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法应用场景") from exc

    return await execute_inspection(
        db=db,
        user_id=_current_user_id(user),
        document_name=filename,
        text=text,
        project_id=project_id,
        application_scenario=application_scenario,
        taboo_words_input=taboo_words,
    )


@router.post("/parse", response_model=InspectionParseResponse)
async def parse_inspection_file(
    file: UploadFile = File(..., description="待解析的工程文档"),
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionParseResponse:
    """上传并解析文档基础信息，创建后续体检使用的会话。"""
    filename, content_bytes, text = await _read_inspection_upload_text(file)
    user_id = _current_user_id(user)
    detected_type = _detect_document_type(filename, text)
    file_format = _inspection_file_format(filename)
    record = await create_pending_inspection_record(
        db=db,
        user_id=user_id,
        document_name=filename,
        document_type=detected_type["document_type"],
        document_type_label=detected_type["document_type_label"],
        text=text,
    )
    session = _create_inspection_session(
        user_id=user_id,
        filename=filename,
        file_size=len(content_bytes),
        file_format=file_format,
        document_type=detected_type["document_type"],
        document_type_label=detected_type["document_type_label"],
        text=text,
        record_id=record.id,
    )

    return InspectionParseResponse(
        session_id=session["id"],
        file=InspectionParseFileResponse(
            name=filename,
            size=len(content_bytes),
            format=file_format,
            document_type=session["document_type"],
            documentType=session["document_type"],
            document_type_label=session["document_type_label"],
            text_preview=session["text_preview"],
            parsed_content=text,
        ),
    )


@router.post("/sessions/{session_id}/inspect", response_model=InspectionReportResponse)
async def inspect_session(
    session_id: str,
    body: InspectionSessionInspectRequest,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionReportResponse:
    """基于已解析的会话执行智能体检。"""
    user_id = _current_user_id(user)
    session = _get_session_for_user(session_id, user_id)

    detected_type = session["document_type"]
    effective_scenario = body.application_scenario or detected_type
    if effective_scenario == "unknown":
        effective_scenario = "bidding"

    return await execute_inspection(
        db=db,
        user_id=_current_user_id(user),
        document_name=session["filename"],
        text=session["text"],
        project_id=body.project_id,
        application_scenario=effective_scenario,
        taboo_words_input=body.taboo_words,
        record_id=session.get("record_id"),
    )


@router.get("/records", response_model=InspectionRecordListResponse)
async def list_records(
    project_id: str | None = None,
    risk_level: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 10,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionRecordListResponse:
    """获取体检记录列表（支持按项目和风险等级筛选）"""
    user_id = _current_user_id(user)
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    conditions = [InspectionRecord.user_id == user_id]
    if project_id:
        conditions.append(InspectionRecord.project_id == project_id)
    if risk_level:
        conditions.append(InspectionRecord.overall_risk == risk_level)
    if keyword and keyword.strip():
        escaped = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(InspectionRecord.document_name.ilike(f"%{escaped}%", escape="\\"))

    total = await db.scalar(select(func.count()).select_from(InspectionRecord).where(*conditions)) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    result = await db.execute(
        select(InspectionRecord)
        .where(*conditions)
        .order_by(desc(InspectionRecord.created_at), desc(InspectionRecord.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = result.scalars().all()

    return InspectionRecordListResponse(
        items=[
            InspectionRecordListItem(
                id=r.id,
                document_name=r.document_name,
                project_id=r.project_id,
                overall_risk=r.overall_risk,
                summary=r.summary,
                issue_count=len(r.issues or []),
                document_type=r.document_type,
                document_type_label=r.document_type_label,
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ],
        pagination=InspectionRecordPagination(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get("/records/{record_id}")
async def get_record(
    record_id: int,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> dict[str, Any]:
    """获取单条体检记录详情"""
    user_id = _current_user_id(user)
    record = await db.scalar(select(InspectionRecord).where(InspectionRecord.id == record_id, InspectionRecord.user_id == user_id))
    if record is not None:
        return {
            "id": record.id,
            "document_name": record.document_name,
            "project_id": record.project_id,
            "overall_risk": record.overall_risk,
            "summary": record.summary,
            "issues": record.issues or [],
            "regulation_refs": record.regulation_refs or [],
            "document_type": record.document_type,
            "document_type_label": record.document_type_label,
            "text_preview": record.text_preview,
            "parsed_content": decrypt_text(record.parsed_content),
            "created_at": record.created_at.isoformat(),
        }
    raise HTTPException(status_code=404, detail="记录不存在")


@router.get("/records/{record_id}/report.pdf")
async def download_record_report_pdf(
    record_id: int,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> Response:
    """下载单条体检记录的 PDF 审查报告。"""
    user_id = _current_user_id(user)
    record = await db.scalar(select(InspectionRecord).where(InspectionRecord.id == record_id, InspectionRecord.user_id == user_id))
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")

    filename = f"{_strip_document_extension(record.document_name)}审查报告.pdf"
    return Response(
        content=render_report_pdf(record),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/records/{record_id}/inspect", response_model=InspectionReportResponse)
async def inspect_record(
    record_id: int,
    body: InspectionSessionInspectRequest,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionReportResponse:
    """基于已解析但未审查的记录执行智能体检。"""
    user_id = _current_user_id(user)
    record = await db.scalar(select(InspectionRecord).where(InspectionRecord.id == record_id, InspectionRecord.user_id == user_id))
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    if not record.parsed_content.strip():
        raise HTTPException(status_code=400, detail="该记录缺少完整解析正文，请重新上传后审查")

    decrypted_text = decrypt_text(record.parsed_content)

    return await execute_inspection(
        db=db,
        user_id=_current_user_id(user),
        document_name=record.document_name,
        text=decrypted_text,
        project_id=body.project_id,
        application_scenario=record.document_type,
        taboo_words_input=body.taboo_words,
        record_id=record.id,
    )


@router.delete("/records/{record_id}", status_code=204)
async def delete_record(
    record_id: int,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> Response:
    """删除单条体检记录。"""
    user_id = _current_user_id(user)
    record = await db.scalar(select(InspectionRecord).where(InspectionRecord.id == record_id, InspectionRecord.user_id == user_id))
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(record)
    await db.commit()
    return Response(status_code=204)


@router.get("/stats/history", response_model=HistoryStatsResponse)
async def get_history_stats(
    project_id: str = "default",
    range: str = "7d",
    user: CurrentUserContext = Depends(get_current_user),
) -> HistoryStatsResponse:
    """获取历史统计（MVP: 近7天，按天聚合）。"""
    if range != "7d":
        raise HTTPException(status_code=400, detail="当前仅支持 range=7d")

    user_id = _current_user_id(user)
    scoped_records = [
        record
        for record in _inspection_records
        if record.get("project_id") == project_id and record.get("user_id") == user_id
    ]
    return _aggregate_history_stats(scoped_records, days=7)


@router.post("/records/{record_id}/burn")
async def burn_record_content(
    record_id: int,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    user_id = _current_user_id(user)
    result = await db.execute(
        select(InspectionRecord).where(
            InspectionRecord.id == record_id,
            InspectionRecord.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    record.parsed_content = ""
    await db.commit()
    return {"id": record.id, "burned": True}
