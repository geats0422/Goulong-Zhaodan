from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent_auth import get_api_key_user, require_api_scope
from core.database import get_db_session
from models import InspectionRecord
from services.agent_job_service import create_job, get_job
from services.knowledge_retrieval import retrieve_regulation_base

router = APIRouter(prefix="/api/v1/agent", tags=["Agent API"])


class CreateJobRequest(BaseModel):
    input_payload: dict | None = None


def _job_response(job) -> dict:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "job_type": job.job_type,
        "progress": job.progress,
        "message": job.message,
        "input_payload": job.input_payload,
        "result_payload": job.result_payload,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/me")
async def agent_me(user: dict = Depends(get_api_key_user)):
    return {
        "user_id": user["user_id"],
        "api_key_id": user["api_key_id"],
        "scopes": user["scopes"],
    }


@router.post("/jobs/inspect", status_code=201)
async def create_inspect_job(
    body: CreateJobRequest | None = None,
    user: dict = Depends(require_api_scope("inspection:run")),
    db: AsyncSession = Depends(get_db_session),
):
    job = await create_job(
        db,
        user_id=user["user_id"],
        api_key_id=user["api_key_id"],
        job_type="inspect",
        input_payload=body.input_payload if body else None,
    )
    return _job_response(job)


@router.post("/jobs/parse", status_code=201)
async def create_parse_job(
    body: CreateJobRequest | None = None,
    user: dict = Depends(require_api_scope("inspection:run")),
    db: AsyncSession = Depends(get_db_session),
):
    job = await create_job(
        db,
        user_id=user["user_id"],
        api_key_id=user["api_key_id"],
        job_type="parse",
        input_payload=body.input_payload if body else None,
    )
    return _job_response(job)


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user: dict = Depends(get_api_key_user),
    db: AsyncSession = Depends(get_db_session),
):
    job = await get_job(db, job_id, user["user_id"])
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return _job_response(job)


def _record_list_item(record: InspectionRecord) -> dict:
    return {
        "id": record.id,
        "document_name": record.document_name,
        "document_type": record.document_type,
        "document_type_label": record.document_type_label,
        "overall_risk": record.overall_risk,
        "summary": record.summary,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _record_detail(record: InspectionRecord) -> dict:
    return {
        "id": record.id,
        "document_name": record.document_name,
        "document_type": record.document_type,
        "document_type_label": record.document_type_label,
        "overall_risk": record.overall_risk,
        "summary": record.summary,
        "issues": record.issues,
        "regulation_refs": record.regulation_refs,
        "text_preview": record.text_preview,
        "quota_consumed": record.quota_consumed,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/records")
async def list_records(
    user: dict = Depends(require_api_scope("inspection:read")),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(InspectionRecord)
        .where(InspectionRecord.user_id == user["user_id"])
        .order_by(InspectionRecord.created_at.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [_record_list_item(r) for r in records]


@router.get("/records/{record_id}")
async def get_record_detail(
    record_id: int,
    user: dict = Depends(require_api_scope("inspection:read")),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(InspectionRecord).where(
        InspectionRecord.id == record_id,
        InspectionRecord.user_id == user["user_id"],
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="record_not_found")
    return _record_detail(record)


class KnowledgeSearchRequest(BaseModel):
    query: str
    application_scenario: str = "bidding"
    limit: int = 10


@router.post("/knowledge/search")
async def search_knowledge(
    body: KnowledgeSearchRequest,
    user: dict = Depends(require_api_scope("knowledge:read")),
    db: AsyncSession = Depends(get_db_session),
):
    return await retrieve_regulation_base(
        db,
        user_id=user["user_id"],
        application_scenario=body.application_scenario,
        limit=body.limit,
    )
