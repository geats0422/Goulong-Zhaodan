from __future__ import annotations

from collections.abc import Callable, Coroutine

from app.core.database import async_session
from app.services.agent_job_service import (
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
)


async def _run_inspect(ctx, job_id: str) -> dict:
    """从 job.input_payload 取文档正文，运行体检，返回结果摘要。"""
    from sqlalchemy import select

    from app.services.inspection_runner import execute_inspection
    from app.models.api_keys import AgentJob

    async with async_session() as db:
        job = (await db.execute(select(AgentJob).where(AgentJob.job_id == job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"job_not_found: {job_id}")

        payload = job.input_payload or {}
        text = payload.get("text")
        if not text or len(str(text).strip()) < 10:
            raise ValueError("input_payload.text 缺失或过短，无法体检")

        report = await execute_inspection(
            db=db,
            user_id=job.user_id,
            document_name=payload.get("document_name", "未命名文档"),
            text=text,
            project_id=payload.get("project_id", "default"),
            application_scenario=payload.get("application_scenario", "bidding"),
            taboo_words_input=payload.get("taboo_words", ""),
        )
        return {
            "record_id": report.id,
            "overall_risk": report.overall_risk,
            "document_name": report.document_name,
        }


async def _run_parse(ctx, job_id: str) -> dict:
    """从 job.input_payload 解析正文并创建 pending record，供后续 record_id 体检。"""
    import base64

    from sqlalchemy import select

    from app.api.v1.inspection import _detect_document_type, _extract_inspection_text, _validate_inspection_filename
    from app.core.file_magic import validate_file_magic
    from app.models.api_keys import AgentJob
    from app.services.inspection_runner import create_pending_inspection_record

    async with async_session() as db:
        job = (await db.execute(select(AgentJob).where(AgentJob.job_id == job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"job_not_found: {job_id}")

        payload = job.input_payload or {}
        document_name = payload.get("document_name") or payload.get("filename") or "未命名文档.txt"
        text = payload.get("text")
        if not text and payload.get("content_base64"):
            try:
                content = base64.b64decode(str(payload["content_base64"]), validate=True)
            except Exception as exc:
                raise ValueError("input_payload.content_base64 不是有效的 base64") from exc
            _validate_inspection_filename(document_name)
            validate_file_magic(document_name, content)
            text = _extract_inspection_text(document_name, content)

        if not text or len(str(text).strip()) < 10:
            raise ValueError("input_payload.text 缺失或过短，无法解析")

        text = str(text)
        detected_type = _detect_document_type(document_name, text)
        record = await create_pending_inspection_record(
            db=db,
            user_id=job.user_id,
            document_name=document_name,
            document_type=detected_type["document_type"],
            document_type_label=detected_type["document_type_label"],
            text=text,
            project_id=payload.get("project_id", "default"),
        )
        return {
            "record_id": record.id,
            "document_name": document_name,
            "document_type": detected_type["document_type"],
            "document_type_label": detected_type["document_type_label"],
            "text_preview": text[:500],
        }


async def _run_knowledge_upload(ctx, job_id: str) -> dict:
    """从 job.input_payload 上传知识库文件，复用现有知识库入库 handler。"""
    import base64
    import io

    from sqlalchemy import select
    from starlette.datastructures import UploadFile

    from app.api.v1.knowledge import upload_and_ingest
    from app.models.api_keys import AgentJob

    async with async_session() as db:
        job = (await db.execute(select(AgentJob).where(AgentJob.job_id == job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"job_not_found: {job_id}")

        payload = job.input_payload or {}
        encoded_content = payload.get("content_base64")
        if not encoded_content:
            raise ValueError("input_payload.content_base64 缺失，无法上传知识库文件")
        try:
            content = base64.b64decode(str(encoded_content), validate=True)
        except Exception as exc:
            raise ValueError("input_payload.content_base64 不是有效的 base64") from exc
        if not content:
            raise ValueError("input_payload.content_base64 为空，无法上传知识库文件")

        filename = payload.get("document_name") or payload.get("filename") or "knowledge.pdf"
        upload_file = UploadFile(file=io.BytesIO(content), filename=filename)
        from app.core.auth import CurrentUserContext

        fake_user = CurrentUserContext(user_id=job.user_id)
        result = await upload_and_ingest(
            file=upload_file,  # type: ignore[arg-type]
            category=payload.get("category", "general"),
            application_scenario=payload.get("application_scenario", "bidding"),
            subcategory_id=payload.get("subcategory_id"),
            subcategory_name=payload.get("subcategory_name"),
            db=db,
            user=fake_user,
        )
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return dict(result)


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
