"""Document-job state machine, artifact validation, and caller-owned transactions.

All mutating functions only ``flush``. Callers must wrap them in
``async with session.begin()``. Artifact preparation performs file I/O before
that transaction and returns immutable, validated boundary objects.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import re
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.data_encryption import decrypt_sensitive_artifact
from app.models.document_job import DOCUMENT_JOB_TYPES, DOCUMENT_PARSER_ENGINES, DocumentProcessingJob
from app.services.document_quality import assess_text_quality, quality_thresholds_from_settings
from app.services.file_storage import iter_file_chunks


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ERROR_MESSAGES = {
    "conversion_failed": "文档解析失败，请重试",
    "convert_to_pdf_required": "该文档需先转换为 PDF 后重新上传",
    "file_read": "无法读取已上传的文档",
    "indexing_failed": "文档索引失败，请稍后重试",
    "inspection_failed": "文档审查失败，请稍后重试",
    "deprecated_application_scenario": "历史招投标记录已归档，无法按旧场景重审",
    "invalid_utf8": "文本文件必须使用 UTF-8 编码",
    "low_quality": "文档文本质量不足",
    "mineru_failed": "MinerU 文档解析失败，请稍后重试",
    "mineru_low_quality": "MinerU 解析结果质量不足",
    "parse_timeout": "文档解析超时，请稍后重试",
    "processing_failed": "文档处理失败，请稍后重试",
}
_TRANSITIONS = {
    "queued": frozenset({"detecting", "indexing"}),
    "detecting": frozenset({"parsing_local", "parsing_mineru"}),
    "parsing_local": frozenset({"parsing_mineru", "indexing", "inspecting"}),
    "parsing_mineru": frozenset({"indexing", "inspecting"}),
    "indexing": frozenset({"inspecting", "succeeded"}),
    "inspecting": frozenset({"succeeded"}),
}


class DocumentJobNotFoundError(LookupError):
    status_code = 404


class InvalidStorageIdentifierError(ValueError):
    pass


class InvalidDocumentJobTransitionError(ValueError):
    pass


class RetryLimitExceededError(ValueError):
    pass


class DocumentJobOwnershipError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    user_id: uuid.UUID
    source_path: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class MarkdownArtifact:
    user_id: uuid.UUID
    markdown_path: str
    markdown_hash: str
    markdown: str
    parser_engine: str = "mineru"


@dataclass(frozen=True, slots=True)
class MarkdownCacheCandidate:
    user_id: uuid.UUID
    content_hash: str
    parser_version: str
    markdown_path: str
    markdown_hash: str
    parser_engine: str


ChunkReader = Callable[[str], AsyncIterator[bytes]]


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _lease_write_guard(lease_owner: str | None, timestamp: datetime.datetime):
    if lease_owner is None:
        return DocumentProcessingJob.lease_owner.is_(None)
    return (
        (DocumentProcessingJob.lease_owner == lease_owner)
        & (DocumentProcessingJob.lease_expires_at.is_not(None))
        & (DocumentProcessingJob.lease_expires_at > timestamp)
    )


def validate_storage_identifier(value: str, user_id: uuid.UUID) -> None:
    if not value or "\\" in value or "\x00" in value or ":" in value:
        raise InvalidStorageIdentifierError("非法存储标识")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InvalidStorageIdentifierError("非法存储标识")
    if len(path.parts) < 3 or path.parts[:2] != ("users", str(user_id)):
        raise InvalidStorageIdentifierError("存储标识不属于当前用户")


def _validate_hash(value: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError("哈希必须是小写 SHA-256")


async def _default_chunk_reader(path: str) -> AsyncIterator[bytes]:
    iterator = iter(iter_file_chunks(path))
    sentinel = object()
    while True:
        chunk = await asyncio.to_thread(next, iterator, sentinel)
        if chunk is sentinel:
            return
        if not isinstance(chunk, bytes):
            raise TypeError("存储读取器必须返回 bytes")
        yield chunk


async def _read_and_hash(
    path: str,
    *,
    chunk_reader: ChunkReader,
    collect: bool,
    max_bytes: int,
) -> tuple[str, bytes]:
    digest = hashlib.sha256()
    content = bytearray()
    total = 0
    async for chunk in chunk_reader(path):
        if not isinstance(chunk, bytes):
            raise ValueError("存储读取器必须返回 bytes")
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("存储产物超过大小限制")
        digest.update(chunk)
        if collect:
            content.extend(chunk)
    return digest.hexdigest(), bytes(content)


async def prepare_source_artifact(
    user_id: uuid.UUID,
    source_path: str,
    expected_hash: str,
    *,
    chunk_reader: ChunkReader = _default_chunk_reader,
) -> SourceArtifact:
    """流式复核受控源文件；必须在数据库事务开始前调用。"""
    validate_storage_identifier(source_path, user_id)
    _validate_hash(expected_hash)
    actual_hash, _ = await _read_and_hash(
        source_path,
        chunk_reader=chunk_reader,
        collect=False,
        max_bytes=settings.document_max_parse_bytes,
    )
    if actual_hash != expected_hash:
        raise ValueError("源文件内容哈希不一致")
    return SourceArtifact(user_id, source_path, actual_hash)


async def prepare_markdown_artifact(
    user_id: uuid.UUID,
    markdown_path: str,
    *,
    parser_engine: str = "mineru",
    expected_hash: str | None = None,
    require_expected_hash: bool = True,
    chunk_reader: ChunkReader = _default_chunk_reader,
) -> MarkdownArtifact:
    """读取、计算哈希、验证 UTF-8 与质量；必须在数据库事务外调用。"""
    validate_storage_identifier(markdown_path, user_id)
    if parser_engine not in DOCUMENT_PARSER_ENGINES:
        raise ValueError("不支持的解析引擎")
    if expected_hash is not None:
        _validate_hash(expected_hash)
    _, envelope = await _read_and_hash(
        markdown_path,
        chunk_reader=chunk_reader,
        collect=True,
        max_bytes=settings.mineru_max_markdown_bytes * 2 + 1024,
    )
    content = decrypt_sensitive_artifact(
        envelope,
        allow_legacy_plaintext=settings.environment != "production",
    )
    if len(content) > settings.mineru_max_markdown_bytes:
        raise ValueError("Markdown 产物超过大小限制")
    actual_hash = hashlib.sha256(content).hexdigest()
    if require_expected_hash and expected_hash is not None and actual_hash != expected_hash:
        raise ValueError("Markdown 内容哈希不一致")
    try:
        markdown = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Markdown 不是有效 UTF-8") from None
    quality = assess_text_quality(markdown, quality_thresholds_from_settings(settings))
    if not quality.is_acceptable:
        raise ValueError("Markdown 文本质量不足")
    return MarkdownArtifact(user_id, markdown_path, actual_hash, markdown, parser_engine)


def sanitize_document_job_error(code: str) -> tuple[str, str]:
    stable = code if code in _SAFE_ERROR_MESSAGES else "processing_failed"
    return stable, _SAFE_ERROR_MESSAGES[stable]


def validate_reusable_markdown(
    *,
    source: Any,
    markdown: Any,
    parser_version: str,
    cached_content_hash: str,
    cached_parser_version: str,
) -> None:
    """Enforce cache ownership and exact source/parser identity after artifact validation."""
    if markdown.user_id != source.user_id:
        raise ValueError("不得跨用户复用 Markdown")
    if cached_content_hash != source.content_hash:
        raise ValueError("缓存内容哈希不匹配")
    if cached_parser_version != parser_version:
        raise ValueError("缓存解析版本不匹配")


def validate_document_job_transition(
    *,
    current_stage: str,
    target_stage: str,
    job_type: str,
    current_progress: int,
    target_progress: int,
    has_valid_markdown: bool,
) -> None:
    if job_type not in DOCUMENT_JOB_TYPES:
        raise InvalidDocumentJobTransitionError("任务类型无效")
    if "inspecting" in {current_stage, target_stage} and job_type != "inspection":
        raise InvalidDocumentJobTransitionError("仅体检任务可进入或停留在审查阶段")
    if current_stage == target_stage:
        if target_progress <= current_progress:
            raise InvalidDocumentJobTransitionError("同阶段进度必须单调递增")
        return
    if target_stage not in _TRANSITIONS.get(current_stage, frozenset()):
        raise InvalidDocumentJobTransitionError("非法阶段转换")
    if target_stage in {"indexing", "inspecting", "succeeded"} and not has_valid_markdown:
        raise InvalidDocumentJobTransitionError("进入该阶段前必须有有效 Markdown")
    if target_stage == "inspecting" and job_type != "inspection":
        raise InvalidDocumentJobTransitionError("仅体检任务可进入审查阶段")
    if target_stage == "succeeded" and job_type == "inspection" and current_stage != "inspecting":
        raise InvalidDocumentJobTransitionError("体检任务必须完成审查")


async def create_document_job(
    db: AsyncSession,
    *,
    source: SourceArtifact,
    job_type: str,
    file_type: str,
    parser_version: str = "1",
    reusable_markdown: MarkdownArtifact | None = None,
    cached_content_hash: str | None = None,
    cached_parser_version: str | None = None,
    knowledge_version_id: int | None = None,
    inspection_record_id: int | None = None,
) -> DocumentProcessingJob:
    """Add and flush a queued job. The caller owns commit/rollback."""
    if job_type not in DOCUMENT_JOB_TYPES:
        raise ValueError("不支持的文档任务类型")
    if reusable_markdown is not None:
        if cached_content_hash is None or cached_parser_version is None:
            raise ValueError("复用 Markdown 必须携带缓存身份")
        validate_reusable_markdown(
            source=source,
            markdown=reusable_markdown,
            parser_version=parser_version,
            cached_content_hash=cached_content_hash,
            cached_parser_version=cached_parser_version,
        )
    await _validate_related_resource_ownership(
        db,
        user_id=source.user_id,
        knowledge_version_id=knowledge_version_id,
        inspection_record_id=inspection_record_id,
    )
    job = DocumentProcessingJob(
        job_id=f"doc_job_{uuid.uuid4().hex}",
        user_id=source.user_id,
        job_type=job_type,
        source_path=source.source_path,
        content_hash=source.content_hash,
        file_type=file_type.lower().lstrip("."),
        parser_version=parser_version,
        dispatch_pending=True,
        dispatch_retry_count=0,
        next_dispatch_at=_now(),
        knowledge_version_id=knowledge_version_id,
        inspection_record_id=inspection_record_id,
        markdown_path=reusable_markdown.markdown_path if reusable_markdown else None,
        markdown_hash=reusable_markdown.markdown_hash if reusable_markdown else None,
        parser_engine=reusable_markdown.parser_engine if reusable_markdown else None,
    )
    db.add(job)
    await db.flush()
    return job


async def _validate_related_resource_ownership(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    knowledge_version_id: int | None,
    inspection_record_id: int | None,
) -> None:
    from app.models.knowledge import DocumentVersion, InspectionRecord, KnowledgeDocument

    if knowledge_version_id is not None:
        owned_version = await db.scalar(
            select(DocumentVersion.id)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentVersion.document_id)
            .where(
                DocumentVersion.id == knowledge_version_id,
                KnowledgeDocument.owner_type == "user",
                KnowledgeDocument.owner_user_id == user_id,
            )
        )
        if owned_version is None:
            raise DocumentJobOwnershipError("knowledge_version_not_owned")
    if inspection_record_id is not None:
        owned_record = await db.scalar(
            select(InspectionRecord.id).where(
                InspectionRecord.id == inspection_record_id,
                InspectionRecord.user_id == user_id,
            )
        )
        if owned_record is None:
            raise DocumentJobOwnershipError("inspection_record_not_owned")


async def list_markdown_cache_candidates(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    content_hash: str,
    parser_version: str,
    limit: int = 10,
) -> list[MarkdownCacheCandidate]:
    """Read metadata only; validate candidate files after this read transaction ends."""
    _validate_hash(content_hash)
    rows = (
        await db.scalars(
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.user_id == user_id,
                DocumentProcessingJob.content_hash == content_hash,
                DocumentProcessingJob.parser_version == parser_version,
                DocumentProcessingJob.status == "succeeded",
                DocumentProcessingJob.markdown_path.is_not(None),
                DocumentProcessingJob.markdown_hash.is_not(None),
                DocumentProcessingJob.parser_engine.is_not(None),
            )
            .order_by(DocumentProcessingJob.finished_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        MarkdownCacheCandidate(
            user_id=row.user_id,
            content_hash=row.content_hash,
            parser_version=row.parser_version,
            markdown_path=cast(str, row.markdown_path),
            markdown_hash=cast(str, row.markdown_hash),
            parser_engine=cast(str, row.parser_engine),
        )
        for row in rows
    ]


async def get_document_job(db: AsyncSession, job_id: str, user_id: uuid.UUID) -> DocumentProcessingJob:
    job = await db.scalar(
        select(DocumentProcessingJob).where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.user_id == user_id,
        )
    )
    if job is None:
        raise DocumentJobNotFoundError("document_job_not_found")
    return job


async def claim_document_jobs_for_dispatch(
    db: AsyncSession,
    *,
    dispatch_owner: str,
    limit: int = 20,
    claim_seconds: int = 30,
    now: datetime.datetime | None = None,
) -> list[DocumentProcessingJob]:
    """Claim dispatch intents with row locks; caller owns the transaction."""
    timestamp = now or _now()
    claim_expires_at = timestamp + datetime.timedelta(seconds=claim_seconds)
    await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.dispatch_pending.is_(False),
            or_(
                DocumentProcessingJob.status == "queued",
                (
                    (DocumentProcessingJob.status == "running")
                    & (DocumentProcessingJob.lease_expires_at.is_not(None))
                    & (DocumentProcessingJob.lease_expires_at <= timestamp)
                ),
            ),
        )
        .values(dispatch_pending=True, next_dispatch_at=timestamp)
    )
    rows = (
        await db.scalars(
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.dispatch_pending.is_(True),
                DocumentProcessingJob.next_dispatch_at <= timestamp,
                DocumentProcessingJob.status.in_(("queued", "running")),
                or_(
                    DocumentProcessingJob.dispatch_claim_expires_at.is_(None),
                    DocumentProcessingJob.dispatch_claim_expires_at <= timestamp,
                ),
            )
            .order_by(DocumentProcessingJob.next_dispatch_at, DocumentProcessingJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for row in rows:
        row.dispatch_claim_owner = dispatch_owner
        row.dispatch_claim_expires_at = claim_expires_at
    await db.flush()
    return list(rows)


async def mark_document_job_dispatched(
    db: AsyncSession,
    job_id: str,
    *,
    dispatch_owner: str,
) -> bool:
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.dispatch_pending.is_(True),
            DocumentProcessingJob.dispatch_claim_owner == dispatch_owner,
        )
        .values(
            dispatch_pending=False,
            dispatch_claim_owner=None,
            dispatch_claim_expires_at=None,
            updated_at=_now(),
        )
        .returning(DocumentProcessingJob.id)
    )
    await db.flush()
    return result.scalar_one_or_none() is not None


async def mark_document_job_dispatch_failed(
    db: AsyncSession,
    job_id: str,
    *,
    dispatch_owner: str,
    now: datetime.datetime | None = None,
) -> bool:
    timestamp = now or _now()
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.dispatch_pending.is_(True),
            DocumentProcessingJob.dispatch_claim_owner == dispatch_owner,
        )
        .values(
            dispatch_retry_count=DocumentProcessingJob.dispatch_retry_count + 1,
            next_dispatch_at=timestamp + datetime.timedelta(seconds=5),
            dispatch_claim_owner=None,
            dispatch_claim_expires_at=None,
            updated_at=timestamp,
        )
        .returning(DocumentProcessingJob.id)
    )
    await db.flush()
    return result.scalar_one_or_none() is not None


async def claim_document_job_lease(
    db: AsyncSession,
    job_id: str,
    *,
    lease_owner: str,
    lease_seconds: int,
    now: datetime.datetime | None = None,
) -> DocumentProcessingJob | None:
    timestamp = now or _now()
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.status.in_(("queued", "running")),
            or_(
                DocumentProcessingJob.lease_expires_at.is_(None),
                DocumentProcessingJob.lease_expires_at <= timestamp,
            ),
        )
        .values(
            lease_owner=lease_owner,
            lease_expires_at=timestamp + datetime.timedelta(seconds=lease_seconds),
            lease_version=DocumentProcessingJob.lease_version + 1,
            dispatch_pending=False,
            dispatch_claim_owner=None,
            dispatch_claim_expires_at=None,
            updated_at=timestamp,
        )
        .returning(DocumentProcessingJob)
    )
    claimed = result.scalar_one_or_none()
    await db.flush()
    return claimed


async def heartbeat_document_job_lease(
    db: AsyncSession,
    job_id: str,
    *,
    lease_owner: str,
    expected_lease_version: int,
    lease_seconds: int,
    now: datetime.datetime | None = None,
) -> bool:
    timestamp = now or _now()
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.lease_owner == lease_owner,
            DocumentProcessingJob.lease_version == expected_lease_version,
            DocumentProcessingJob.lease_expires_at > timestamp,
            DocumentProcessingJob.status.in_(("queued", "running")),
        )
        .values(
            lease_expires_at=timestamp + datetime.timedelta(seconds=lease_seconds),
            updated_at=timestamp,
        )
        .returning(DocumentProcessingJob.id)
    )
    await db.flush()
    return result.scalar_one_or_none() is not None


async def persist_document_job_mineru_task(
    db: AsyncSession,
    job_id: str,
    *,
    task_id: str,
    upload_state: str,
    lease_owner: str,
    expected_lease_version: int,
) -> DocumentProcessingJob | None:
    """Persist upload intent before PUT and mark it resumable only after PUT."""
    if not task_id or len(task_id) > 200:
        raise ValueError("invalid MinerU task id")
    if upload_state not in {"pending", "uploaded"}:
        raise ValueError("invalid MinerU upload state")
    timestamp = _now()
    statement = update(DocumentProcessingJob).where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.lease_owner == lease_owner,
            DocumentProcessingJob.lease_version == expected_lease_version,
            DocumentProcessingJob.lease_expires_at > timestamp,
            DocumentProcessingJob.status == "running",
        )
    if upload_state == "pending":
        statement = statement.where(
            or_(
                DocumentProcessingJob.mineru_upload_state.is_(None),
                DocumentProcessingJob.mineru_upload_state == "pending",
            )
        )
    else:
        statement = statement.where(
            DocumentProcessingJob.mineru_task_id == task_id,
            DocumentProcessingJob.mineru_upload_state == "pending",
        )
    result = await db.execute(
        statement.values(mineru_task_id=task_id, mineru_upload_state=upload_state, updated_at=timestamp)
        .returning(DocumentProcessingJob)
    )
    await db.flush()
    return result.scalar_one_or_none()


async def clear_document_job_mineru_task(
    db: AsyncSession,
    job_id: str,
    *,
    lease_owner: str,
    expected_lease_version: int,
) -> bool:
    timestamp = _now()
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.lease_owner == lease_owner,
            DocumentProcessingJob.lease_version == expected_lease_version,
            DocumentProcessingJob.lease_expires_at > timestamp,
            DocumentProcessingJob.status == "running",
        )
        .values(mineru_task_id=None, mineru_upload_state=None, updated_at=timestamp)
        .returning(DocumentProcessingJob.id)
    )
    await db.flush()
    return result.scalar_one_or_none() is not None


async def persist_document_job_inspection_state(
    db: AsyncSession,
    job_id: str,
    *,
    user_id: uuid.UUID,
    state: str,
    input_hash: str,
    lease_owner: str,
    expected_lease_version: int,
    result_path: str | None = None,
    result_hash: str | None = None,
) -> DocumentProcessingJob | None:
    """Fence inspection call metadata with the active inspecting lease; caller commits."""
    if state not in {"started", "completed"}:
        raise ValueError("invalid inspection call state")
    _validate_hash(input_hash)
    if state == "completed":
        if result_path is None or result_hash is None:
            raise ValueError("completed inspection requires a result artifact")
        validate_storage_identifier(result_path, user_id)
        _validate_hash(result_hash)
    elif result_path is not None or result_hash is not None:
        raise ValueError("started inspection cannot carry a result artifact")

    timestamp = _now()
    statement = update(DocumentProcessingJob).where(
        DocumentProcessingJob.job_id == job_id,
        DocumentProcessingJob.user_id == user_id,
        DocumentProcessingJob.job_type == "inspection",
        DocumentProcessingJob.stage == "inspecting",
        DocumentProcessingJob.status == "running",
        DocumentProcessingJob.lease_owner == lease_owner,
        DocumentProcessingJob.lease_version == expected_lease_version,
        DocumentProcessingJob.lease_expires_at > timestamp,
    )
    if state == "completed":
        statement = statement.where(
            DocumentProcessingJob.inspection_call_state == "started",
            DocumentProcessingJob.inspection_input_hash == input_hash,
        )
    result = await db.execute(
        statement.values(
            inspection_call_state=state,
            inspection_input_hash=input_hash,
            inspection_result_path=result_path,
            inspection_result_hash=result_hash,
            updated_at=timestamp,
        ).returning(DocumentProcessingJob)
    )
    await db.flush()
    return result.scalar_one_or_none()


async def release_document_job_lease(
    db: AsyncSession,
    job_id: str,
    *,
    lease_owner: str,
    expected_lease_version: int,
    redispatch: bool = False,
) -> bool:
    values: dict[str, Any] = {
        "lease_owner": None,
        "lease_expires_at": None,
        "lease_version": expected_lease_version + 1,
        "updated_at": _now(),
    }
    if redispatch:
        values.update(dispatch_pending=True, next_dispatch_at=_now())
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.lease_owner == lease_owner,
            DocumentProcessingJob.lease_version == expected_lease_version,
            DocumentProcessingJob.status.in_(("queued", "running")),
        )
        .values(**values)
        .returning(DocumentProcessingJob.id)
    )
    await db.flush()
    return result.scalar_one_or_none() is not None


async def cancel_document_job(
    db: AsyncSession,
    job_id: str,
    *,
    lease_owner: str,
    expected_lease_version: int,
) -> DocumentProcessingJob | None:
    timestamp = _now()
    result = await db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.lease_owner == lease_owner,
            DocumentProcessingJob.lease_version == expected_lease_version,
            DocumentProcessingJob.status.in_(("queued", "running")),
        )
        .values(
            status="cancelled",
            finished_at=timestamp,
            lease_owner=None,
            lease_expires_at=None,
            lease_version=expected_lease_version + 1,
            dispatch_pending=False,
            dispatch_claim_owner=None,
            dispatch_claim_expires_at=None,
            error_code=None,
            error_message=None,
            updated_at=timestamp,
        )
        .returning(DocumentProcessingJob)
    )
    cancelled = result.scalar_one_or_none()
    await db.flush()
    return cancelled


async def update_document_job_stage(
    db: AsyncSession,
    job_id: str,
    *,
    expected_stage: str,
    expected_retry_count: int,
    expected_lease_version: int,
    stage: str,
    progress: int,
    lease_owner: str | None = None,
    job_type: str = "knowledge",
    message: str | None = None,
    validated_markdown: MarkdownArtifact | None = None,
) -> DocumentProcessingJob | None:
    validate_document_job_transition(
        current_stage=expected_stage,
        target_stage=stage,
        job_type=job_type,
        current_progress=progress - 1,
        target_progress=progress,
        has_valid_markdown=validated_markdown is not None,
    )
    timestamp = _now()
    values: dict[str, Any] = {
        "status": "running",
        "stage": stage,
        "progress": progress,
        "lease_version": expected_lease_version + 1,
        "updated_at": timestamp,
        "error_code": None,
        "error_message": None,
        "finished_at": None,
    }
    if message is not None:
        values["message"] = message
    if validated_markdown is not None:
        values.update(
            markdown_path=validated_markdown.markdown_path,
            markdown_hash=validated_markdown.markdown_hash,
            parser_engine=validated_markdown.parser_engine,
        )
    statement = (
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.job_type == job_type,
            DocumentProcessingJob.stage == expected_stage,
            DocumentProcessingJob.retry_count == expected_retry_count,
            DocumentProcessingJob.lease_version == expected_lease_version,
            _lease_write_guard(lease_owner, timestamp),
            DocumentProcessingJob.progress < progress,
            DocumentProcessingJob.status.in_(("queued", "running")),
        )
        .values(**values)
        .returning(DocumentProcessingJob)
    )
    result = (await db.execute(statement)).scalar_one_or_none()
    await db.flush()
    return result


async def mark_document_job_failed(
    db: AsyncSession,
    job_id: str,
    *,
    expected_stage: str,
    expected_retry_count: int,
    expected_lease_version: int,
    error_code: str,
    lease_owner: str | None = None,
) -> DocumentProcessingJob | None:
    stable_code, message = sanitize_document_job_error(error_code)
    timestamp = _now()
    statement = (
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.stage == expected_stage,
            DocumentProcessingJob.retry_count == expected_retry_count,
            DocumentProcessingJob.lease_version == expected_lease_version,
            _lease_write_guard(lease_owner, timestamp),
            DocumentProcessingJob.status.in_(("queued", "running")),
        )
        .values(
            status="failed",
            stage="failed",
            lease_version=expected_lease_version + 1,
            lease_owner=None,
            lease_expires_at=None,
            dispatch_pending=False,
            dispatch_claim_owner=None,
            dispatch_claim_expires_at=None,
            index_artifact_path=None,
            index_artifact_hash=None,
            inspection_call_state=None,
            inspection_input_hash=None,
            inspection_result_path=None,
            inspection_result_hash=None,
            mineru_task_id=None,
            mineru_upload_state=None,
            finished_at=timestamp,
            error_code=stable_code,
            error_message=message,
            updated_at=timestamp,
        )
        .returning(DocumentProcessingJob)
    )
    result = (await db.execute(statement)).scalar_one_or_none()
    await db.flush()
    return result


async def mark_document_job_succeeded(
    db: AsyncSession,
    job_id: str,
    *,
    expected_stage: str,
    expected_retry_count: int,
    expected_lease_version: int,
    artifact: MarkdownArtifact,
    lease_owner: str | None = None,
    job_type: str = "knowledge",
    chunk_reader: ChunkReader = _default_chunk_reader,
) -> DocumentProcessingJob | None:
    """Transactional completion entry: verify I/O first, then open a short CAS transaction."""
    if db.in_transaction():
        raise RuntimeError("完成任务前调用方不得预先开启数据库事务")
    verified = await prepare_markdown_artifact(
        artifact.user_id,
        artifact.markdown_path,
        parser_engine=artifact.parser_engine,
        expected_hash=artifact.markdown_hash,
        chunk_reader=chunk_reader,
    )
    validate_document_job_transition(
        current_stage=expected_stage,
        target_stage="succeeded",
        job_type=job_type,
        current_progress=99,
        target_progress=100,
        has_valid_markdown=True,
    )
    async with db.begin():
        return await _mark_document_job_succeeded_cas(
            db,
            job_id,
            expected_stage=expected_stage,
            expected_retry_count=expected_retry_count,
            expected_lease_version=expected_lease_version,
            lease_owner=lease_owner,
            artifact=verified,
            job_type=job_type,
        )


async def _mark_document_job_succeeded_cas(
    db: AsyncSession,
    job_id: str,
    *,
    expected_stage: str,
    expected_retry_count: int,
    expected_lease_version: int,
    artifact: MarkdownArtifact,
    job_type: str,
    lease_owner: str | None = None,
) -> DocumentProcessingJob | None:
    timestamp = _now()
    statement = (
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.job_id == job_id,
            DocumentProcessingJob.user_id == artifact.user_id,
            DocumentProcessingJob.job_type == job_type,
            DocumentProcessingJob.stage == expected_stage,
            DocumentProcessingJob.retry_count == expected_retry_count,
            DocumentProcessingJob.lease_version == expected_lease_version,
            _lease_write_guard(lease_owner, timestamp),
            DocumentProcessingJob.status == "running",
        )
        .values(
            status="succeeded",
            stage="succeeded",
            progress=100,
            lease_version=expected_lease_version + 1,
            lease_owner=None,
            lease_expires_at=None,
            dispatch_pending=False,
            dispatch_claim_owner=None,
            dispatch_claim_expires_at=None,
            parser_engine=artifact.parser_engine,
            markdown_path=artifact.markdown_path,
            markdown_hash=artifact.markdown_hash,
            index_artifact_path=None,
            index_artifact_hash=None,
            inspection_result_path=None,
            inspection_result_hash=None,
            finished_at=timestamp,
            error_code=None,
            error_message=None,
            updated_at=timestamp,
        )
        .returning(DocumentProcessingJob)
    )
    result = (await db.execute(statement)).scalar_one_or_none()
    await db.flush()
    return result


async def retry_document_job(
    db: AsyncSession,
    job_id: str,
    user_id: uuid.UUID,
    *,
    max_retries: int,
    validated_markdown: MarkdownArtifact | None = None,
) -> DocumentProcessingJob:
    job = await db.scalar(
        select(DocumentProcessingJob)
        .where(DocumentProcessingJob.job_id == job_id, DocumentProcessingJob.user_id == user_id)
        .with_for_update()
    )
    if job is None:
        raise DocumentJobNotFoundError("document_job_not_found")
    if job.status != "failed":
        raise InvalidDocumentJobTransitionError("只有失败任务可以重试")
    if job.retry_count >= max_retries:
        raise RetryLimitExceededError("任务重试次数已达上限")
    keep_markdown = (
        validated_markdown is not None
        and validated_markdown.user_id == user_id
        and validated_markdown.markdown_path == job.markdown_path
        and validated_markdown.markdown_hash == job.markdown_hash
    )
    job.retry_count += 1
    job.lease_version += 1
    job.lease_owner = None
    job.lease_expires_at = None
    job.status = "queued"
    job.stage = "queued"
    job.progress = 0
    job.finished_at = None
    job.error_code = None
    job.error_message = None
    job.message = None
    job.dispatch_pending = True
    job.dispatch_retry_count = 0
    job.next_dispatch_at = _now()
    job.dispatch_claim_owner = None
    job.dispatch_claim_expires_at = None
    if not keep_markdown:
        job.markdown_path = None
        job.markdown_hash = None
        job.parser_engine = None
        job.mineru_task_id = None
        job.mineru_upload_state = None
    await db.flush()
    return job
