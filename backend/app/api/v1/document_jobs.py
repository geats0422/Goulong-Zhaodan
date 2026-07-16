from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUserContext, get_current_user
from app.core.database import get_db_session
from app.core.config import settings
from app.core.document_job_retry_rate_limit import (
    RetryRateLimitUnavailableError,
    consume_retry_rate_limit,
)
from app.services.document_job_service import (
    DocumentJobNotFoundError,
    InvalidDocumentJobTransitionError,
    MarkdownArtifact,
    RetryLimitExceededError,
    get_document_job,
    prepare_markdown_artifact,
    retry_document_job,
    sanitize_document_job_error,
)


router = APIRouter(prefix="/document-jobs", tags=["文档任务"])
DOCUMENT_JOB_MAX_RETRIES = 3
_STAGE_MESSAGES = {
    "queued": "任务已排队，等待处理",
    "detecting": "正在识别文档类型",
    "parsing_local": "正在解析文档",
    "parsing_mineru": "正在进行高质量文档解析",
    "indexing": "正在构建文档索引",
    "inspecting": "正在审查文档",
    "succeeded": "文档处理完成",
    "failed": "任务处理失败",
}


class DocumentJobError(BaseModel):
    code: str
    message: str


class DocumentJobResponse(BaseModel):
    id: str
    type: str
    status: str
    stage: str
    progress: int
    message: str
    parser_engine: str | None
    retry_count: int
    max_retries: int
    knowledge_version_id: int | None
    inspection_record_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    finished_at: datetime.datetime | None
    error: DocumentJobError | None


def _response(job) -> DocumentJobResponse:
    error = None
    if job.error_code:
        code, message = sanitize_document_job_error(job.error_code)
        error = DocumentJobError(code=code, message=message)
    message = "任务已取消" if job.status == "cancelled" else _STAGE_MESSAGES.get(job.stage, "文档任务处理中")
    return DocumentJobResponse(
        id=job.job_id,
        type=job.job_type,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        message=message,
        parser_engine=job.parser_engine,
        retry_count=job.retry_count,
        max_retries=DOCUMENT_JOB_MAX_RETRIES,
        knowledge_version_id=job.knowledge_version_id,
        inspection_record_id=job.inspection_record_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        error=error,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档任务不存在")


async def _validated_markdown(job) -> MarkdownArtifact | None:
    if not job.markdown_path or not job.markdown_hash or not job.parser_engine:
        return None
    try:
        return await prepare_markdown_artifact(
            job.user_id,
            job.markdown_path,
            parser_engine=job.parser_engine,
            expected_hash=job.markdown_hash,
        )
    except (OSError, ValueError):
        return None


@router.get("/{job_id}", response_model=DocumentJobResponse)
async def get_document_job_status(
    job_id: str,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentJobResponse:
    try:
        job = await get_document_job(db, job_id, current_user.user_id)
    except DocumentJobNotFoundError:
        raise _not_found() from None
    return _response(job)


@router.post("/{job_id}/retry", response_model=DocumentJobResponse)
async def retry_failed_document_job(
    job_id: str,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentJobResponse:
    try:
        current = await get_document_job(db, job_id, current_user.user_id)
    except DocumentJobNotFoundError:
        raise _not_found() from None
    if current.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务当前不可重试")
    if current.retry_count >= DOCUMENT_JOB_MAX_RETRIES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务重试次数已达上限")

    try:
        allowed = await consume_retry_rate_limit(
            current_user.user_id,
            limit=settings.document_job_retry_rate_limit,
            window_seconds=settings.document_job_retry_rate_limit_window,
        )
    except RetryRateLimitUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="重试服务暂时不可用，请稍后再试",
        ) from None
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="重试请求过于频繁，请稍后再试")

    markdown = await _validated_markdown(current)
    try:
        job = await retry_document_job(
            db,
            job_id,
            current_user.user_id,
            max_retries=DOCUMENT_JOB_MAX_RETRIES,
            validated_markdown=markdown,
        )
        await db.commit()
    except DocumentJobNotFoundError:
        raise _not_found() from None
    except InvalidDocumentJobTransitionError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务当前不可重试") from None
    except RetryLimitExceededError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务重试次数已达上限") from None

    return _response(job)
