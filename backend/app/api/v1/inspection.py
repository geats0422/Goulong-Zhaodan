"""体检台 API 路由"""
from __future__ import annotations

import hashlib
import logging
import tempfile
import re
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import desc, exists, func, or_, select, true
from sqlalchemy.exc import IntegrityError

from app.core.auth import CurrentUserContext, get_current_user
from app.core.constants import validate_application_scenario
from app.core.data_encryption import decrypt_text
from app.core.database import get_db_session
from app.core.file_magic import validate_file_magic
from app.core.quota import require_quota
from app.models.knowledge import InspectionRecord
from app.models.knowledge import InspectionType, KnowledgeDocument
from app.schemas.inspection_types import (
    InspectionTypeCreate,
    InspectionTypeResponse,
    InspectionStep2Submission,
    InspectionTypeUpdate,
)
from app.services.document_job_service import (
    create_document_job,
    prepare_source_artifact,
)
from app.services.file_storage import FileStorageError, delete_file, save_file
from app.services.inspection_runner import (
    DOCUMENT_TYPE_LABELS,
    InspectionReportResponse,
    add_pending_inspection_record,
    execute_inspection,
    validate_inspection_submission,
)
from app.services.markdown_converter import ConversionError, convert_to_markdown
from app.services.report_pdf import render_report_pdf
from app.services.inspection_history import classification_display, is_archived_legacy_record

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspection", tags=["体检台"])
MAX_INSPECTION_FILE_SIZE = 20 * 1024 * 1024
INSPECTION_SESSION_TTL = timedelta(hours=1)
MAX_INSPECTION_SESSIONS = 100
MAX_INSPECTION_SESSIONS_PER_USER = 5
ALLOWED_INSPECTION_EXTENSIONS = {".txt", ".pdf", ".docx"}
DOCUMENT_TYPE_KEYWORDS = {
    "contract": ["合同", "协议", "甲方", "乙方", "民法典", "违约责任", "签订", "付款", "履约", "违约金", "不可抗力"],
    "bidding": ["招标", "投标", "招投标", "采购", "评标", "中标", "投标人", "投标保证金"],
}
DATA_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\(data:image/[^)]*\)", re.IGNORECASE)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)]\([^)]*\)")


# ─── 内存中的解析会话（按 user_id 读取隔离，后续可替换为 Redis） ───
_inspection_sessions: dict[str, dict[str, Any]] = {}


def _current_user_id(user: CurrentUserContext) -> uuid_mod.UUID:
    try:
        return user.user_id
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid user") from exc


def _type_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _serialize_inspection_type(item: InspectionType) -> InspectionTypeResponse:
    return InspectionTypeResponse(
        id=item.id,
        key=item.key,
        name=item.name,
        dimension=item.dimension,
        owner_type=item.owner_type,
        owner_user_id=str(item.owner_user_id) if item.owner_user_id else None,
        enabled=item.enabled,
        created_at=item.created_at.isoformat(),
        updated_at=item.updated_at.isoformat(),
    )


async def _list_inspection_types(
    db,
    dimension: str,
    user_id: uuid_mod.UUID,
    include_disabled: bool = False,
) -> list[InspectionTypeResponse]:
    visibility = or_(InspectionType.owner_type == "system", InspectionType.owner_user_id == user_id)
    enabled_filter = InspectionType.enabled.is_(True) if not include_disabled else true()
    result = await db.scalars(
        select(InspectionType)
        .where(
            InspectionType.dimension == dimension,
            enabled_filter,
            visibility,
        )
        .order_by(InspectionType.owner_type, InspectionType.name, InspectionType.id)
    )
    return [_serialize_inspection_type(item) for item in result.all()]


async def _create_inspection_type(db, dimension: str, body: InspectionTypeCreate, user_id: uuid_mod.UUID) -> InspectionTypeResponse:
    if body.dimension is not None and body.dimension != dimension:
        raise _type_error(422, "invalid_dimension", "类别维度与路由不一致")
    duplicate = await db.scalar(
        select(InspectionType).where(
            InspectionType.dimension == dimension,
            or_(InspectionType.owner_type == "system", InspectionType.owner_user_id == user_id),
            or_(InspectionType.key == body.key, InspectionType.name == body.name),
        )
    )
    if duplicate is not None:
        raise _type_error(409, "duplicate_inspection_type", "类别 key 或名称已存在")
    item = InspectionType(
        key=body.key,
        name=body.name,
        dimension=dimension,
        owner_type="user",
        owner_user_id=user_id,
        enabled=True,
    )
    db.add(item)
    try:
        await db.commit()
        await db.refresh(item)
    except IntegrityError as exc:
        await db.rollback()
        raise _type_error(409, "duplicate_inspection_type", "类别 key 或名称已存在") from exc
    return _serialize_inspection_type(item)


async def _get_owned_or_system_type(db, type_id: int, user_id: uuid_mod.UUID) -> InspectionType:
    item = await db.scalar(
        select(InspectionType).where(
            InspectionType.id == type_id,
            or_(InspectionType.owner_type == "system", InspectionType.owner_user_id == user_id),
        )
    )
    if item is None:
        raise _type_error(404, "inspection_type_not_found", "类别不存在")
    return item


async def _type_is_referenced(db, item: InspectionType) -> bool:
    key_columns = (
        InspectionRecord.detected_engineering_type,
        InspectionRecord.final_engineering_type,
    ) if item.dimension == "engineering" else (
        InspectionRecord.detected_contract_type,
        InspectionRecord.final_contract_type,
    )
    record_reference = await db.scalar(
        select(exists().where(InspectionRecord.user_id == item.owner_user_id, or_(*[column == item.key for column in key_columns])))
    )
    document_column = KnowledgeDocument.engineering_type_key if item.dimension == "engineering" else KnowledgeDocument.contract_type_key
    document_reference = await db.scalar(
        select(exists().where(document_column == item.key, KnowledgeDocument.owner_user_id == item.owner_user_id))
    )
    return bool(record_reference or document_reference)


async def _update_inspection_type(db, type_id: int, body: InspectionTypeUpdate, user_id: uuid_mod.UUID) -> InspectionTypeResponse:
    item = await _get_owned_or_system_type(db, type_id, user_id)
    if item.owner_type == "system":
        raise _type_error(403, "system_type_protected", "系统类别不可修改")
    if (body.key is not None or body.name is not None) and await _type_is_referenced(db, item):
        raise _type_error(409, "inspection_type_in_use", "已被引用的类别只能停用")
    if body.key is not None or body.name is not None:
        duplicate = await db.scalar(
            select(InspectionType).where(
                InspectionType.id != item.id,
                InspectionType.dimension == item.dimension,
                or_(InspectionType.owner_type == "system", InspectionType.owner_user_id == user_id),
                or_(
                    InspectionType.key == (body.key if body.key is not None else item.key),
                    InspectionType.name == (body.name if body.name is not None else item.name),
                ),
            )
        )
        if duplicate is not None:
            raise _type_error(409, "duplicate_inspection_type", "类别 key 或名称已存在")
    if body.key is not None:
        item.key = body.key
    if body.name is not None:
        item.name = body.name
    if body.enabled is not None:
        item.enabled = body.enabled
    try:
        await db.commit()
        await db.refresh(item)
    except IntegrityError as exc:
        await db.rollback()
        raise _type_error(409, "duplicate_inspection_type", "类别 key 或名称已存在") from exc
    return _serialize_inspection_type(item)


async def _delete_inspection_type(db, type_id: int, user_id: uuid_mod.UUID) -> None:
    item = await _get_owned_or_system_type(db, type_id, user_id)
    if item.owner_type == "system":
        raise _type_error(403, "system_type_protected", "系统类别不可删除")
    if await _type_is_referenced(db, item):
        raise _type_error(409, "inspection_type_in_use", "已被引用的类别只能停用")
    await db.delete(item)
    await db.commit()


@router.get("/engineering-types", response_model=list[InspectionTypeResponse])
async def list_engineering_types(
    include_disabled: bool = False,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    return await _list_inspection_types(db, "engineering", _current_user_id(user), include_disabled)


@router.post("/engineering-types", response_model=InspectionTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_engineering_type(body: InspectionTypeCreate, db=Depends(get_db_session), user: CurrentUserContext = Depends(get_current_user)):
    return await _create_inspection_type(db, "engineering", body, _current_user_id(user))


@router.patch("/engineering-types/{type_id}", response_model=InspectionTypeResponse)
async def update_engineering_type(type_id: int, body: InspectionTypeUpdate, db=Depends(get_db_session), user: CurrentUserContext = Depends(get_current_user)):
    item = await _get_owned_or_system_type(db, type_id, _current_user_id(user))
    if item.dimension != "engineering":
        raise _type_error(404, "inspection_type_not_found", "类别不存在")
    return await _update_inspection_type(db, type_id, body, _current_user_id(user))


@router.delete("/engineering-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engineering_type(type_id: int, db=Depends(get_db_session), user: CurrentUserContext = Depends(get_current_user)):
    item = await _get_owned_or_system_type(db, type_id, _current_user_id(user))
    if item.dimension != "engineering":
        raise _type_error(404, "inspection_type_not_found", "类别不存在")
    await _delete_inspection_type(db, type_id, _current_user_id(user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/contract-types", response_model=list[InspectionTypeResponse])
async def list_contract_types(
    include_disabled: bool = False,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
):
    return await _list_inspection_types(db, "contract", _current_user_id(user), include_disabled)


@router.post("/contract-types", response_model=InspectionTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_contract_type(body: InspectionTypeCreate, db=Depends(get_db_session), user: CurrentUserContext = Depends(get_current_user)):
    return await _create_inspection_type(db, "contract", body, _current_user_id(user))


@router.patch("/contract-types/{type_id}", response_model=InspectionTypeResponse)
async def update_contract_type(type_id: int, body: InspectionTypeUpdate, db=Depends(get_db_session), user: CurrentUserContext = Depends(get_current_user)):
    item = await _get_owned_or_system_type(db, type_id, _current_user_id(user))
    if item.dimension != "contract":
        raise _type_error(404, "inspection_type_not_found", "类别不存在")
    return await _update_inspection_type(db, type_id, body, _current_user_id(user))


@router.delete("/contract-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract_type(type_id: int, db=Depends(get_db_session), user: CurrentUserContext = Depends(get_current_user)):
    item = await _get_owned_or_system_type(db, type_id, _current_user_id(user))
    if item.dimension != "contract":
        raise _type_error(404, "inspection_type_not_found", "类别不存在")
    await _delete_inspection_type(db, type_id, _current_user_id(user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validate_inspection_filename(filename: str) -> None:
    dot_idx = filename.rfind(".")
    ext = filename[dot_idx:].lower() if dot_idx != -1 else ""
    if ext == ".doc":
        raise HTTPException(status_code=400, detail="暂不支持 .doc 格式，请先在 Word 中另存为 .docx 后再上传")
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

    if scores["contract"] == 0:
        return {
            "document_type": "unknown",
            "document_type_label": DOCUMENT_TYPE_LABELS["unknown"],
            "confidence": "low",
        }
    document_type = "contract"
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
    """读取体检上传文件，并返回已消费的原始字节与解码文本。

    仅保留给同步入口（``/upload``）使用；``/parse`` 已改为异步文档处理入口，
    PDF/Word 不再在请求线程内同步解析。
    """
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


async def _read_bounded_inspection_upload(file: UploadFile) -> tuple[str, str, bytes]:
    """流式读取受界上传：校验扩展名、大小与 magic bytes，不做内容解析。

    返回 ``(filename, ext, content_bytes)``。解析（PDF/Word → Markdown）交由
    后台 worker 的统一文档管线完成，避免请求线程同步调用解析器。
    """
    filename = file.filename or "unknown"
    _validate_inspection_filename(filename)
    ext = _inspection_file_format(filename)
    try:
        content = await file.read(MAX_INSPECTION_FILE_SIZE + 1)
    except Exception as exc:
        _logger.exception("文件读取失败: %s", filename)
        raise HTTPException(status_code=400, detail="文件无法解析") from exc
    if len(content) > MAX_INSPECTION_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过 20MB 限制")
    try:
        validate_file_magic(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return filename, ext, content


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


class InspectionSessionInspectRequest(InspectionStep2Submission):
    """会话审查请求"""

    project_id: str = "default"
    taboo_words: str = ""
    application_scenario: str | None = None


class ContractClassificationResponse(BaseModel):
    engineering_type_key: str
    contract_type_key: str
    confidence: str
    evidence: list[str]
    source: str
    requires_confirmation: bool


def _classification_response_from_record(record: InspectionRecord) -> ContractClassificationResponse | None:
    if not record.detected_engineering_type or not record.detected_contract_type:
        return None
    return ContractClassificationResponse(
        engineering_type_key=record.final_engineering_type or record.detected_engineering_type,
        contract_type_key=record.final_contract_type or record.detected_contract_type,
        confidence=record.classification_confidence or "low",
        evidence=record.classification_evidence or [],
        source=record.classification_source or "fallback",
        requires_confirmation=(record.classification_confidence or "low") != "high",
    )


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
    classification: ContractClassificationResponse


class InspectionParseResponse(BaseModel):
    """文件解析会话响应"""

    session_id: str
    job_id: str
    file: InspectionParseFileResponse
    status: str = "processing"


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
    uploaded_docs: int
    completed_docs: int
    hit_docs: int
    failed_docs: int
    pending_docs: int
    hit_rate: float
    quota_consumed: int


class HistoryStatsTrend(BaseModel):
    dates: list[str]
    uploaded_docs: list[int]
    completed_docs: list[int]
    hit_docs: list[int]
    failed_docs: list[int]
    pending_docs: list[int]
    hit_rate: list[float]
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


def _aggregate_history_stats(records: list[InspectionRecord], days: int = 7) -> HistoryStatsResponse:
    buckets = {
        d.isoformat(): {
            "uploaded_docs": 0,
            "completed_docs": 0,
            "hit_docs": 0,
            "failed_docs": 0,
            "pending_docs": 0,
            "quota_consumed": 0,
        }
        for d in _build_last_n_dates(days)
    }

    for record in records:
        created_at = _safe_parse_date(record.created_at)
        if created_at is None:
            continue

        key = created_at.isoformat()
        if key not in buckets:
            continue

        buckets[key]["uploaded_docs"] += 1
        if record.status == "completed":
            buckets[key]["completed_docs"] += 1
        elif record.status == "failed":
            buckets[key]["failed_docs"] += 1
        elif record.status in {"uploaded", "processing"}:
            buckets[key]["pending_docs"] += 1
        if record.status == "completed" and record.issues:
            buckets[key]["hit_docs"] += 1
        buckets[key]["quota_consumed"] += _safe_int(record.quota_consumed or 0)

    dates = list(buckets.keys())
    uploaded_docs_series = [buckets[d]["uploaded_docs"] for d in dates]
    completed_docs_series = [buckets[d]["completed_docs"] for d in dates]
    hit_docs_series = [buckets[d]["hit_docs"] for d in dates]
    failed_docs_series = [buckets[d]["failed_docs"] for d in dates]
    pending_docs_series = [buckets[d]["pending_docs"] for d in dates]
    quota_series = [buckets[d]["quota_consumed"] for d in dates]
    rate_series = [_calc_rate(hit, completed) for hit, completed in zip(hit_docs_series, completed_docs_series)]

    uploaded_docs = sum(uploaded_docs_series)
    completed_docs = sum(completed_docs_series)
    hit_docs = sum(hit_docs_series)
    failed_docs = sum(failed_docs_series)
    pending_docs = sum(pending_docs_series)
    quota_consumed = sum(quota_series)

    return HistoryStatsResponse(
        range="7d",
        timezone="Asia/Shanghai",
        summary=HistoryStatsSummary(
            uploaded_docs=uploaded_docs,
            completed_docs=completed_docs,
            hit_docs=hit_docs,
            failed_docs=failed_docs,
            pending_docs=pending_docs,
            hit_rate=_calc_rate(hit_docs, completed_docs),
            quota_consumed=quota_consumed,
        ),
        trend=HistoryStatsTrend(
            dates=dates,
            uploaded_docs=uploaded_docs_series,
            completed_docs=completed_docs_series,
            hit_docs=hit_docs_series,
            failed_docs=failed_docs_series,
            pending_docs=pending_docs_series,
            hit_rate=rate_series,
            quota_consumed=quota_series,
        ),
    )


@router.post("/upload", response_model=InspectionReportResponse)
async def upload_and_inspect(
    file: UploadFile = File(..., description="待体检的工程文档"),
    project_id: str = Form(default="default"),
    application_scenario: str = Form(default="contract"),
    taboo_words: str = Form(default=""),
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionReportResponse:
    """
    上传文档并执行智能体检。

    支持格式：txt、pdf、docx；旧版 .doc 请先在 Word 中另存为 .docx。
    """
    await require_quota(db, _current_user_id(user))
    filename, _, text = await _read_inspection_upload_text(file)

    try:
        validate_application_scenario(application_scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法应用场景") from exc
    if application_scenario != "contract":
        raise _type_error(400, "deprecated_application_scenario", "新体检仅支持合同场景")

    return await execute_inspection(
        db=db,
        user_id=_current_user_id(user),
        document_name=filename,
        text=text,
        project_id=project_id,
        application_scenario=application_scenario,
        taboo_words_input=taboo_words,
    )


@router.post("/parse", status_code=202, response_model=InspectionParseResponse)
async def parse_inspection_file(
    file: UploadFile = File(..., description="待解析的工程文档"),
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionParseResponse:
    """上传文档到受控存储并创建异步审查任务（DocumentProcessingJob）。

    解析与审查统一由后台 worker 完成；前端通过返回的 ``job_id`` 轮询
    ``/api/v1/document-jobs/{job_id}`` 跟踪进度。PDF/Word 不再在请求线程内
    同步解析直达审查引擎。``/upload`` 仍保留同步体检入口以向后兼容。
    """
    await require_quota(db, _current_user_id(user))
    filename, ext, content = await _read_bounded_inspection_upload(file)
    user_id = _current_user_id(user)

    content_hash = hashlib.sha256(content).hexdigest()
    source_path = f"users/{user_id}/documents/{uuid4().hex}.{ext}"
    try:
        save_file(source_path, content)
    except FileStorageError as exc:
        raise HTTPException(status_code=503, detail="文件存储服务暂时不可用") from exc

    try:
        source = await prepare_source_artifact(user_id, source_path, content_hash)
        record = await add_pending_inspection_record(
            db=db,
            user_id=user_id,
            document_name=filename,
            document_type="contract",
            document_type_label=DOCUMENT_TYPE_LABELS["contract"],
            text="",
        )
        job = await create_document_job(
            db,
            source=source,
            job_type="inspection",
            file_type=ext,
            inspection_record_id=record.id,
        )
        await db.commit()
    except Exception:
        # 复核或事务失败时清理已落盘的源文件，避免产生无人认领的孤儿产物。
        delete_file(source_path)
        raise

    session = _create_inspection_session(
        user_id=user_id,
        filename=filename,
        file_size=len(content),
        file_format=ext,
        document_type="contract",
        document_type_label=DOCUMENT_TYPE_LABELS["contract"],
        text="",
        record_id=record.id,
    )

    return InspectionParseResponse(
        session_id=session["id"],
        job_id=job.job_id,
        file=InspectionParseFileResponse(
            name=filename,
            size=len(content),
            format=ext,
            document_type="contract",
            documentType="contract",
            document_type_label=DOCUMENT_TYPE_LABELS["contract"],
            text_preview="",
            parsed_content="",
            classification=ContractClassificationResponse(
                engineering_type_key="general-engineering",
                contract_type_key="other",
                confidence="low",
                evidence=[],
                source="pending",
                requires_confirmation=True,
            ),
        ),
        status="processing",
    )


@router.post("/sessions/{session_id}/inspect", response_model=InspectionReportResponse)
async def inspect_session(
    session_id: str,
    body: InspectionSessionInspectRequest,
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> InspectionReportResponse:
    """基于已解析的会话执行智能体检。"""
    await require_quota(db, _current_user_id(user))
    user_id = _current_user_id(user)
    session = _get_session_for_user(session_id, user_id)

    selection = None
    if body.engineering_type_key is not None or body.contract_type_key is not None or body.knowledge_document_ids is not None:
        selection = await validate_inspection_submission(
            db,
            user_id=user_id,
            engineering_type_key=body.engineering_type_key,
            contract_type_key=body.contract_type_key,
            knowledge_document_ids=body.knowledge_document_ids,
        )

    detected_type = session["document_type"]
    effective_scenario = body.application_scenario or detected_type
    if effective_scenario == "unknown":
        effective_scenario = "contract"
    if effective_scenario != "contract":
        raise _type_error(400, "deprecated_application_scenario", "新体检仅支持合同场景")

    execute_kwargs = {
        "db": db,
        "user_id": user_id,
        "document_name": session["filename"],
        "text": session["text"],
        "project_id": body.project_id,
        "application_scenario": effective_scenario,
        "taboo_words_input": body.taboo_words,
        "record_id": session.get("record_id"),
    }
    if selection is not None:
        execute_kwargs.update(
            engineering_type_key=selection["engineering_type_key"],
            contract_type_key=selection["contract_type_key"],
            knowledge_document_ids=body.knowledge_document_ids,
        )
    return await execute_inspection(**execute_kwargs)


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
        classification = _classification_response_from_record(record)
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
            "classification": classification.model_dump() if classification else None,
            "classification_display": classification_display(record),
            "final_engineering_type": record.final_engineering_type,
            "final_contract_type": record.final_contract_type,
            "classification_confidence": record.classification_confidence,
            "rule_package_key": record.rule_package_key,
            "rule_package_keys": [record.rule_package_key] if record.rule_package_key else [],
            "engineering_type_snapshot": record.engineering_type_snapshot,
            "contract_type_snapshot": record.contract_type_snapshot,
            "knowledge_sources_snapshot": record.knowledge_sources_snapshot or [],
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
    if body.application_scenario == "bidding":
        raise _type_error(400, "deprecated_application_scenario", "新体检仅支持合同场景")
    if is_archived_legacy_record(record):
        raise _type_error(400, "deprecated_application_scenario", "历史招投标记录不可按旧场景重审")
    if not record.parsed_content.strip():
        raise HTTPException(status_code=400, detail="该记录缺少完整解析正文，请重新上传后审查")

    decrypted_text = decrypt_text(record.parsed_content)

    execute_kwargs = {
        "db": db,
        "user_id": user_id,
        "document_name": record.document_name,
        "text": decrypted_text,
        "project_id": body.project_id,
        "application_scenario": record.document_type,
        "taboo_words_input": body.taboo_words,
        "record_id": record.id,
    }
    if body.engineering_type_key is not None or body.contract_type_key is not None or body.knowledge_document_ids is not None:
        selection = await validate_inspection_submission(
            db, user_id=user_id, engineering_type_key=body.engineering_type_key,
            contract_type_key=body.contract_type_key, knowledge_document_ids=body.knowledge_document_ids,
        )
        execute_kwargs.update(
            engineering_type_key=selection["engineering_type_key"],
            contract_type_key=selection["contract_type_key"],
            knowledge_document_ids=body.knowledge_document_ids,
        )
    return await execute_inspection(**execute_kwargs)


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
    if is_archived_legacy_record(record):
        raise _type_error(400, "deprecated_application_scenario", "历史招投标记录只读，不可删除")

    await db.delete(record)
    await db.commit()
    return Response(status_code=204)


@router.get("/stats/history", response_model=HistoryStatsResponse)
async def get_history_stats(
    project_id: str | None = None,
    range: str = "7d",
    db=Depends(get_db_session),
    user: CurrentUserContext = Depends(get_current_user),
) -> HistoryStatsResponse:
    """获取历史统计（MVP: 近7天，按天聚合）。"""
    if range != "7d":
        raise HTTPException(status_code=400, detail="当前仅支持 range=7d")

    user_id = _current_user_id(user)
    conditions = [InspectionRecord.user_id == user_id]
    if project_id is not None:
        conditions.append(InspectionRecord.project_id == project_id)
    start = datetime.combine(_build_last_n_dates(7)[0], datetime.min.time())
    scoped_records = list(
        (await db.scalars(select(InspectionRecord).where(*conditions, InspectionRecord.created_at >= start))).all()
    )
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
    if is_archived_legacy_record(record):
        raise _type_error(400, "deprecated_application_scenario", "历史招投标记录只读，不可销毁")
    record.parsed_content = ""
    await db.commit()
    return {"id": record.id, "burned": True}
