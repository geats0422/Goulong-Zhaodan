from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_auth import get_api_key_user, require_api_scope
from app.core.constants import validate_application_scenario
from app.core.data_encryption import decrypt_text
from app.core.database import get_db_session
from app.core.quota import require_quota
from app.models import InspectionRecord
from app.services.inspection_runner import (
    InspectionReportResponse,
    classify_inspection_document,
    create_pending_inspection_record,
    execute_inspection,
)
from app.services.contract_classifier import screen_contract_rules
from app.services.inspection_history import classification_display
from app.services.agent_job_service import create_job, get_job
from app.services.knowledge_retrieval import retrieve_regulation_base
from app.api.v1.inspection import ContractClassificationResponse, _read_inspection_upload_text

router = APIRouter(prefix="/api/v1/agent", tags=["Agent API"])


class CreateJobRequest(BaseModel):
    input_payload: dict | None = None


def _validate_agent_job_scenario(body: CreateJobRequest | None) -> None:
    scenario = (body.input_payload or {}).get("application_scenario") if body else None
    if scenario == "bidding":
        raise HTTPException(
            status_code=400,
            detail={"code": "deprecated_application_scenario", "message": "新 Agent 任务仅支持合同场景"},
        )
    if scenario is not None and scenario != "contract":
        raise HTTPException(status_code=400, detail="非法应用场景")


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
    _validate_agent_job_scenario(body)
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
    _validate_agent_job_scenario(body)
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
        "classification_evidence": record.classification_evidence or [],
        "classification_display": classification_display(record),
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
    application_scenario: str = "contract"
    limit: int = 10
    engineering_type_key: str | None = None
    contract_type_key: str | None = None

    @field_validator("limit")
    @classmethod
    def clamp_limit(cls, v: int) -> int:
        return max(1, min(100, v))


@router.post("/knowledge/search")
async def search_knowledge(
    body: KnowledgeSearchRequest,
    user: dict = Depends(require_api_scope("knowledge:read")),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        validate_application_scenario(body.application_scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法应用场景") from exc
    if body.application_scenario != "contract":
        raise HTTPException(
            status_code=400,
            detail={"code": "deprecated_application_scenario", "message": "新知识检索仅支持合同场景"},
        )
    return await retrieve_regulation_base(
        db,
        user_id=user["user_id"],
        application_scenario=body.application_scenario,
        limit=body.limit,
        engineering_type_key=body.engineering_type_key,
        contract_type_key=body.contract_type_key,
    )


class AgentParseResponse(BaseModel):
    record_id: int
    document_name: str
    document_type: str
    document_type_label: str
    text_preview: str
    classification: ContractClassificationResponse


@router.post("/parse", response_model=AgentParseResponse)
async def agent_parse(
    file: UploadFile = File(..., description="待解析的工程文档"),
    project_id: str = Form(default="default"),
    user: dict = Depends(require_api_scope("inspection:run")),
    db: AsyncSession = Depends(get_db_session),
) -> AgentParseResponse:
    """同步解析：MCP / Agent 客户端上传文件，返回可二次体检的 record_id。"""
    filename, _, text = await _read_inspection_upload_text(file)
    classification = await classify_inspection_document(
        document_name=filename,
        text=text,
        rule_screening=screen_contract_rules(filename=filename, text=text),
    )
    record = await create_pending_inspection_record(
        db=db,
        user_id=user["user_id"],
        document_name=filename,
        document_type="contract",
        document_type_label="合同",
        text=text,
        project_id=project_id,
        classification=classification,
    )
    return AgentParseResponse(
        record_id=record.id,
        document_name=filename,
        document_type="contract",
        document_type_label="合同",
        text_preview=text[:500],
        classification=ContractClassificationResponse(**classification.__dict__),
    )


class AgentInspectRequest(BaseModel):
    document_name: str | None = None
    text: str | None = None
    record_id: int | None = None
    application_scenario: str = "contract"
    taboo_words: str = ""
    project_id: str = "default"
    engineering_type_key: str | None = None
    contract_type_key: str | None = None

    @field_validator("document_name")
    @classmethod
    def _validate_document_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value or len(value) > 200:
            raise ValueError("document_name 长度须为 1-200 字符")
        return value


@router.post("/inspect", response_model=InspectionReportResponse)
async def agent_inspect(
    body: AgentInspectRequest,
    user: dict = Depends(require_api_scope("inspection:run")),
    db: AsyncSession = Depends(get_db_session),
) -> InspectionReportResponse:
    """同步体检：MCP / Agent 客户端直接传入文档正文，一次调用返回完整审查报告。"""
    await require_quota(db, user["user_id"])
    document_name = body.document_name
    text = body.text
    application_scenario = body.application_scenario

    if application_scenario == "bidding":
        raise HTTPException(
            status_code=400,
            detail={"code": "deprecated_application_scenario", "message": "新体检仅支持合同场景"},
        )

    if body.record_id is not None:
        record = await db.scalar(
            select(InspectionRecord).where(
                InspectionRecord.id == body.record_id,
                InspectionRecord.user_id == user["user_id"],
            )
        )
        if record is None:
            raise HTTPException(status_code=404, detail="record_not_found")
        if record.document_type == "bidding" or record.classification_source == "archived_legacy":
            raise HTTPException(
                status_code=400,
                detail={"code": "deprecated_application_scenario", "message": "历史招投标记录不可按旧场景重审"},
            )
        if not record.parsed_content.strip():
            raise HTTPException(status_code=400, detail="该记录缺少完整解析正文，请重新上传后审查")
        document_name = record.document_name
        text = decrypt_text(record.parsed_content)
        application_scenario = "contract"

    if document_name is None or text is None:
        raise HTTPException(status_code=400, detail="请提供 record_id 或 document_name + text")

    try:
        validate_application_scenario(application_scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法应用场景") from exc

    if len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文件内容过短，无法体检")

    return await execute_inspection(
        db=db,
        user_id=user["user_id"],
        document_name=document_name,
        text=text,
        project_id=body.project_id,
        application_scenario=application_scenario,
        taboo_words_input=body.taboo_words,
        record_id=body.record_id,
        engineering_type_key=body.engineering_type_key,
        contract_type_key=body.contract_type_key,
    )
