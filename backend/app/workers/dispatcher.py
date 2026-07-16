from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from app.core.database import async_session
from app.services.document_job_service import (
    claim_document_jobs_for_dispatch,
    mark_document_job_dispatch_failed,
    mark_document_job_dispatched,
)


DOCUMENT_JOB_TASK = "document_processing_task"


def document_job_arq_id(job_id: str, retry_count: int, dispatch_retry_count: int) -> str:
    return f"document-job:{job_id}:{retry_count}:{dispatch_retry_count}"


async def dispatch_pending_document_jobs(
    redis: Any,
    *,
    session_factory: Callable[..., Any] = async_session,
    owner: str | None = None,
    limit: int = 20,
) -> int:
    dispatch_owner = owner or f"dispatcher-{uuid.uuid4().hex}"
    async with session_factory() as db:
        async with db.begin():
            jobs = await claim_document_jobs_for_dispatch(
                db,
                dispatch_owner=dispatch_owner,
                limit=limit,
            )

    dispatched = 0
    for job in jobs:
        try:
            enqueued = await redis.enqueue_job(
                DOCUMENT_JOB_TASK,
                job_id=job.job_id,
                _job_id=document_job_arq_id(job.job_id, job.retry_count, job.dispatch_retry_count),
            )
        except Exception:
            async with session_factory() as db:
                async with db.begin():
                    await mark_document_job_dispatch_failed(
                        db,
                        job.job_id,
                        dispatch_owner=dispatch_owner,
                    )
            continue

        if enqueued is None:
            async with session_factory() as db:
                async with db.begin():
                    await mark_document_job_dispatch_failed(
                        db,
                        job.job_id,
                        dispatch_owner=dispatch_owner,
                    )
            continue

        async with session_factory() as db:
            async with db.begin():
                confirmed = await mark_document_job_dispatched(
                    db,
                    job.job_id,
                    dispatch_owner=dispatch_owner,
                )
        if confirmed:
            dispatched += 1
    return dispatched


async def document_job_dispatcher_task(ctx: dict[str, Any]) -> dict[str, int]:
    return {"dispatched": await dispatch_pending_document_jobs(ctx["redis"])}
