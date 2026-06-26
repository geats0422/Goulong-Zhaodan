from __future__ import annotations

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_keys import AgentJob


async def enqueue_job(task_name: str, job_id: str) -> None:
    pass


async def create_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
    job_type: str,
    input_payload: dict | None = None,
) -> AgentJob:
    job_id = f"job_{uuid.uuid4().hex}"
    job = AgentJob(
        job_id=job_id,
        user_id=user_id,
        api_key_id=api_key_id,
        job_type=job_type,
        status="queued",
        progress=0,
        input_payload=input_payload,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        await enqueue_job(f"{job_type}_document_task", job.id)
    except Exception:
        pass

    return job


async def get_job(
    db: AsyncSession,
    job_id: str,
    user_id: uuid.UUID,
) -> AgentJob | None:
    stmt = select(AgentJob).where(
        AgentJob.job_id == job_id,
        AgentJob.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: str,
    progress: int | None = None,
    message: str | None = None,
    result_payload: dict | None = None,
    error_message: str | None = None,
) -> AgentJob | None:
    stmt = select(AgentJob).where(AgentJob.job_id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = status
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.message = message
    if result_payload is not None:
        job.result_payload = result_payload
    if error_message is not None:
        job.error_message = error_message

    await db.commit()
    await db.refresh(job)
    return job


async def mark_job_running(
    db: AsyncSession,
    job_id: str,
) -> AgentJob | None:
    return await update_job_status(db, job_id, status="running")


async def mark_job_succeeded(
    db: AsyncSession,
    job_id: str,
    result_payload: dict | None = None,
) -> AgentJob | None:
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    job = await update_job_status(
        db,
        job_id,
        status="succeeded",
        result_payload=result_payload,
    )
    if job is None:
        return None
    job.finished_at = now
    await db.commit()
    await db.refresh(job)
    return job


async def mark_job_failed(
    db: AsyncSession,
    job_id: str,
    error_message: str,
) -> AgentJob | None:
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    job = await update_job_status(
        db,
        job_id,
        status="failed",
        error_message=error_message,
    )
    if job is None:
        return None
    job.finished_at = now
    await db.commit()
    await db.refresh(job)
    return job
