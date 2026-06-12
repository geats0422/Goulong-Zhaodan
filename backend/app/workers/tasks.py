from __future__ import annotations

from collections.abc import Callable, Coroutine

from app.core.database import async_session
from app.services.agent_job_service import (
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)


async def _run_inspect(ctx, job_id: str) -> dict:
    return {"status": "completed"}


async def _run_parse(ctx, job_id: str) -> dict:
    return {"status": "completed"}


async def _run_knowledge_upload(ctx, job_id: str) -> dict:
    return {"status": "completed"}


async def _execute_task(
    ctx,
    job_id: str,
    runner: Callable[..., Coroutine],
) -> None:
    async with async_session() as db:
        await mark_job_running(db, job_id)
        try:
            result = await runner(ctx, job_id)
            await mark_job_succeeded(db, job_id, result_payload=result)
        except Exception as exc:
            await mark_job_failed(db, job_id, error_message=str(exc))


async def inspect_document_task(ctx, job_id: str):
    await _execute_task(ctx, job_id, _run_inspect)


async def parse_document_task(ctx, job_id: str):
    await _execute_task(ctx, job_id, _run_parse)


async def knowledge_upload_task(ctx, job_id: str):
    await _execute_task(ctx, job_id, _run_knowledge_upload)
