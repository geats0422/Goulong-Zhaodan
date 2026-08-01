"""体检执行核心 — 从 router 层下沉的业务逻辑（多 Agent 审查流水线）。

inspection.py 与 agent.py 共同引用；workers/tasks.py 的异步 runner 也复用，
避免跨进程 import router 模块。
"""
from __future__ import annotations

import logging
import hashlib
import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.inspector import run_inspection
from app.core.data_encryption import encrypt_text
from app.core.deps import InspectionDeps
from app.models.knowledge import (
    DocumentVersion,
    InspectionRecord,
    InspectionType,
    KnowledgeDocument,
    KnowledgeDocumentSetting,
    TabooWord,
)
from app.services.knowledge_retrieval import retrieve_regulation_base
from app.services.contract_classifier import ContractClassification, classify_contract
from app.services.contract_classifier import screen_contract_rules
from app.services.risk_policy import finalize_overall_risk

_logger = logging.getLogger(__name__)
ENGINEERING_TYPE_NAMES = {
    "building-construction": "房建施工", "municipal-road": "市政道路",
    "decoration-renovation": "装饰装修", "mechanical-electrical-installation": "机电安装",
    "steel-structure": "钢结构", "general-engineering": "通用工程",
}
CONTRACT_TYPE_NAMES = {
    "labor-subcontract": "劳务分包", "professional-subcontract": "专业工程分包", "other": "其他类",
}


async def validate_inspection_submission(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    engineering_type_key: str | None,
    contract_type_key: str | None,
    knowledge_document_ids: list[int] | None,
) -> dict[str, Any]:
    """校验 Step 2 的最终类别和知识库选择，拒绝跨维度及越权值。"""
    engineering_type_key = engineering_type_key or "general-engineering"
    contract_type_key = contract_type_key or "other"

    async def load_type(key: str, dimension: str, code: str) -> InspectionType:
        item = await db.scalar(select(InspectionType).where(
            InspectionType.key == key,
            InspectionType.dimension == dimension,
            InspectionType.enabled.is_(True),
            ((InspectionType.owner_type == "system") | ((InspectionType.owner_type == "user") & (InspectionType.owner_user_id == user_id))),
        ))
        if item is None:
            raise HTTPException(status_code=422, detail={"code": code, "message": "类别不存在、已停用或无权使用"})
        return item

    engineering = await load_type(engineering_type_key, "engineering", "invalid_engineering_type")
    contract = await load_type(contract_type_key, "contract", "invalid_contract_type")
    documents = []
    if knowledge_document_ids:
        if len(set(knowledge_document_ids)) != len(knowledge_document_ids):
            raise HTTPException(status_code=422, detail={"code": "invalid_knowledge_document", "message": "知识库文档 ID 不得重复"})
        documents = list((await db.scalars(select(KnowledgeDocument).outerjoin(
            DocumentVersion, KnowledgeDocument.current_version_id == DocumentVersion.id,
        ).outerjoin(
            KnowledgeDocumentSetting,
            (KnowledgeDocumentSetting.document_id == KnowledgeDocument.id)
            & (KnowledgeDocumentSetting.user_id == user_id),
        ).where(
            KnowledgeDocument.id.in_(knowledge_document_ids),
            KnowledgeDocument.application_scenario == "contract",
            KnowledgeDocument.is_active.is_(True),
            DocumentVersion.status == "completed",
            (
                (KnowledgeDocument.owner_type == "system")
                | (
                    (KnowledgeDocument.owner_type == "user")
                    & (KnowledgeDocument.owner_user_id == user_id)
                    & (KnowledgeDocumentSetting.id.is_(None) | KnowledgeDocumentSetting.enabled.is_(True))
                )
            ),
        ))).all())
        if {doc.id for doc in documents} != set(knowledge_document_ids):
            raise HTTPException(status_code=422, detail={"code": "invalid_knowledge_document", "message": "知识库文档不存在、已停用或无权使用"})
        if len({doc.owner_type for doc in documents}) > 1:
            raise HTTPException(status_code=422, detail={"code": "invalid_knowledge_document", "message": "用户知识库与系统默认知识库不可混用"})
    return {
        "engineering_type_key": engineering.key,
        "contract_type_key": contract.key,
        "engineering_type_snapshot": engineering.name,
        "contract_type_snapshot": contract.name,
        "documents": documents,
    }


def classification_record_values(
    classification: ContractClassification, regulation_base: dict[str, Any] | None = None
) -> dict[str, Any]:
    base = regulation_base or {}
    return {
        "detected_engineering_type": classification.engineering_type_key,
        "final_engineering_type": None,
        "detected_contract_type": classification.contract_type_key,
        "final_contract_type": None,
        "classification_confidence": classification.confidence,
        "classification_source": classification.source,
        "classification_evidence": list(classification.evidence),
        "rule_package_key": base.get("rule_package_key"),
        "rule_package_keys_snapshot": list(base.get("rule_package_keys", [])),
        "engineering_type_snapshot": ENGINEERING_TYPE_NAMES.get(classification.engineering_type_key),
        "contract_type_snapshot": CONTRACT_TYPE_NAMES.get(classification.contract_type_key),
        "knowledge_sources_snapshot": [
            dict(source) for source in base.get("sources", []) if isinstance(source, dict)
        ],
    }


async def classify_inspection_document(
    *, document_name: str, text: str, rule_screening: dict[str, Any] | None = None
) -> ContractClassification:
    """解析/审查流水线共享的分类入口，避免 API 绕过业务服务。"""
    return await classify_contract(filename=document_name, text=text, rule_screening=rule_screening)

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "contract": "合同",
    "bidding": "招投标文件",
    "unknown": "未知类型",
}


class InspectionReportResponse(BaseModel):
    """体检报告响应。"""

    id: int
    overall_risk: str
    summary: str
    issues: list[dict[str, Any]]
    regulation_refs: list[str]
    document_name: str
    document_type: str = ""
    document_type_label: str = ""
    classification: dict[str, Any] | None = None
    final_engineering_type: str | None = None
    final_contract_type: str | None = None
    classification_confidence: str | None = None
    rule_package_key: str | None = None
    rule_package_keys: list[str] = Field(default_factory=list)
    knowledge_sources_snapshot: list[dict[str, Any]] = Field(default_factory=list)


def merge_unique_words(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for word in group:
            normalized = word.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                merged.append(normalized)
    return merged


async def add_pending_inspection_record(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    document_name: str,
    document_type: str,
    document_type_label: str,
    text: str,
    project_id: str = "default",
    classification: ContractClassification | None = None,
) -> InspectionRecord:
    """在调用方事务中追加一条 pending 记录（仅 ``flush``，不 commit/refresh）。

    异步文档处理入口（如 ``/inspection/parse``）需要把 InspectionRecord 的创建
    与 DocumentProcessingJob 的创建编排进同一事务，原子落库以避免悬空记录或孤儿
    任务。调用方负责 ``commit`` / ``refresh`` / 更新内存缓存。同步入口仍应使用
    :func:`create_pending_inspection_record`。
    """
    record = InspectionRecord(
        user_id=user_id,
        document_name=document_name,
        document_type=document_type,
        document_type_label=document_type_label,
        project_id=project_id,
        status="processing",
        overall_risk="pending",
        summary="文件已解析，等待审查",
        issues=[],
        regulation_refs=[],
        text_preview=text[:500],
        parsed_content=encrypt_text(text),
        quota_consumed=0,
    )
    if classification is not None:
        for field_name, value in classification_record_values(classification).items():
            setattr(record, field_name, value)
    db.add(record)
    await db.flush()
    return record


async def create_pending_inspection_record(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    document_name: str,
    document_type: str,
    document_type_label: str,
    text: str,
    project_id: str = "default",
    classification: ContractClassification | None = None,
) -> InspectionRecord:
    """落库一条 pending 记录（已解析、待审查）。"""
    record = await add_pending_inspection_record(
        db=db,
        user_id=user_id,
        document_name=document_name,
        document_type=document_type,
        document_type_label=document_type_label,
        text=text,
        project_id=project_id,
        classification=classification,
    )
    await db.commit()
    await db.refresh(record)
    return record


async def load_user_taboo_words(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(select(TabooWord.word).where(TabooWord.user_id == user_id).order_by(TabooWord.id))
    return list(result.scalars().all())


def allowed_regulation_refs(regulation_base: dict[str, Any], taboo_words: list[str]) -> set[str]:
    refs = {
        str(source.get("title", "")).strip()
        for source in regulation_base.get("sources", [])
        if str(source.get("title", "")).strip()
    }
    refs.update(f"违禁词:{word}" for word in taboo_words if word)
    return refs


def sanitize_inspection_result_refs(result: Any, allowed_refs: set[str]) -> None:
    result.regulation_refs = [ref for ref in result.regulation_refs if ref in allowed_refs]
    for issue in result.issues:
        ref = issue.get("regulation_ref") or issue.get("citation")
        if ref and ref not in allowed_refs:
            issue.pop("regulation_ref", None)
            issue.pop("citation", None)


async def execute_inspection(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    document_name: str,
    text: str,
    project_id: str,
    application_scenario: str,
    taboo_words_input: str = "",
    record_id: int | None = None,
    engineering_type_key: str | None = None,
    contract_type_key: str | None = None,
    knowledge_document_ids: list[int] | None = None,
) -> InspectionReportResponse:
    """公共审查执行：加载违禁词 → 召回知识库 → 运行 Agent → 保存记录 → 返回报告。"""

    if application_scenario == "bidding":
        raise HTTPException(
            status_code=400,
            detail={"code": "deprecated_application_scenario", "message": "新体检仅支持合同场景"},
        )
    if application_scenario != "contract":
        raise HTTPException(status_code=400, detail="非法应用场景")
    selection = None
    if engineering_type_key is not None or contract_type_key is not None or knowledge_document_ids is not None:
        selection = await validate_inspection_submission(
            db, user_id=user_id, engineering_type_key=engineering_type_key,
            contract_type_key=contract_type_key, knowledge_document_ids=knowledge_document_ids,
        )
    existing_record = None
    if record_id is not None:
        existing_record = await db.scalar(
            select(InspectionRecord).with_for_update().where(
                InspectionRecord.id == record_id,
                InspectionRecord.user_id == user_id,
            )
        )
        if existing_record is not None and existing_record.status == "completed":
            raise HTTPException(status_code=409, detail={"code": "inspection_already_completed", "message": "该报告已完成，不能重复提交"})
        if existing_record is not None and (
            existing_record.document_type == "bidding"
            or existing_record.classification_source == "archived_legacy"
        ):
            raise HTTPException(
                status_code=400,
                detail={"code": "deprecated_application_scenario", "message": "历史招投标记录不可按旧场景重审"},
            )

    classification = await classify_inspection_document(
        document_name=document_name,
        text=text,
        rule_screening=screen_contract_rules(filename=document_name, text=text),
    )
    engineering_type_key = (
        engineering_type_key
        or (existing_record.final_engineering_type if existing_record is not None else None)
        or (existing_record.detected_engineering_type if existing_record is not None else None)
        or classification.engineering_type_key
    )
    contract_type_key = (
        contract_type_key
        or (existing_record.final_contract_type if existing_record is not None else None)
        or (existing_record.detected_contract_type if existing_record is not None else None)
        or classification.contract_type_key
    )
    if selection is not None:
        engineering_type_key = selection["engineering_type_key"]
        contract_type_key = selection["contract_type_key"]
    saved_taboo_words = await load_user_taboo_words(db, user_id)
    temporary_taboo_words = [w.strip() for w in taboo_words_input.split(",") if w.strip()]
    taboo_list = merge_unique_words(saved_taboo_words, temporary_taboo_words)
    retrieval_kwargs = {"document_ids": knowledge_document_ids} if knowledge_document_ids is not None else {}
    regulation_base = await retrieve_regulation_base(
        db,
        user_id=user_id,
        application_scenario=application_scenario,
        limit=8,
        engineering_type_key=engineering_type_key,
        contract_type_key=contract_type_key,
        **retrieval_kwargs,
    )

    deps = InspectionDeps(
        project_id=project_id,
        user_id=str(user_id),
        document_name=document_name,
        application_scenario=application_scenario,
        regulation_base=regulation_base,
        taboo_words=taboo_list or None,
        db=db,
        usage_attempt_id=(
            f"record:{record_id}" if record_id is not None else f"inspection:{uuid.uuid4().hex}"
        ),
        usage_input_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )

    try:
        result = await run_inspection(text, deps)
    except Exception as exc:
        _logger.exception("智能审查引擎异常")
        raise HTTPException(
            status_code=502,
            detail="智能审查引擎不可用，请稍后重试",
        ) from exc
    sanitize_inspection_result_refs(result, allowed_regulation_refs(regulation_base, taboo_list))

    # 任务11：服务端按问题最高严重等级最终化 overall_risk，所有 API/历史/PDF 消费此归一化值。
    final_overall_risk = finalize_overall_risk(result.overall_risk, result.issues)

    record = None
    if record_id is not None:
        record = await db.scalar(select(InspectionRecord).where(InspectionRecord.id == record_id, InspectionRecord.user_id == user_id))
    if record is None:
        record = InspectionRecord(user_id=user_id, document_name=document_name)
        db.add(record)

    record.document_name = document_name
    record.document_type = application_scenario
    record.document_type_label = DOCUMENT_TYPE_LABELS.get(application_scenario, application_scenario)
    record.project_id = project_id
    record.status = "completed"
    record.overall_risk = final_overall_risk
    record.summary = result.summary
    record.issues = result.issues
    record.regulation_refs = result.regulation_refs
    record.text_preview = text[:500]
    record.parsed_content = encrypt_text(text)
    record.quota_consumed = getattr(result, "total_quota_consumed", 0) or max(1, len(text) // 500)
    record_values = classification_record_values(classification, regulation_base)
    record_values.update(
        {
            "final_engineering_type": engineering_type_key,
            "final_contract_type": contract_type_key,
            "engineering_type_snapshot": (
                ENGINEERING_TYPE_NAMES.get(engineering_type_key)
                or (existing_record.engineering_type_snapshot if existing_record is not None else None)
                or engineering_type_key
            ),
            "contract_type_snapshot": (
                CONTRACT_TYPE_NAMES.get(contract_type_key)
                or (existing_record.contract_type_snapshot if existing_record is not None else None)
                or contract_type_key
            ),
        }
    )
    if existing_record is not None:
        # 重审不得抹掉历史 detected、置信度与证据：旧记录的检测结果优先保留。
        record_values.update(
            {
                "detected_engineering_type": existing_record.detected_engineering_type or record_values["detected_engineering_type"],
                "detected_contract_type": existing_record.detected_contract_type or record_values["detected_contract_type"],
                "classification_confidence": existing_record.classification_confidence or record_values["classification_confidence"],
                "classification_evidence": existing_record.classification_evidence or record_values["classification_evidence"],
                "classification_source": existing_record.classification_source or record_values["classification_source"],
                "engineering_type_snapshot": existing_record.engineering_type_snapshot or record_values["engineering_type_snapshot"],
                "contract_type_snapshot": existing_record.contract_type_snapshot or record_values["contract_type_snapshot"],
            }
        )
    if selection is not None:
        # 手动确认的类别快照与 manual 来源必须最后写入，不被旧记录快照覆盖。
        record_values.update(
            {
                "classification_source": "manual",
                "engineering_type_snapshot": selection["engineering_type_snapshot"],
                "contract_type_snapshot": selection["contract_type_snapshot"],
            }
        )
    record_values["rule_package_keys_snapshot"] = list(
        regulation_base.get("rule_package_keys", [])
    )
    for field_name, value in record_values.items():
        setattr(record, field_name, value)

    await db.commit()
    await db.refresh(record)

    return InspectionReportResponse(
        id=record.id,
        overall_risk=final_overall_risk,
        summary=result.summary,
        issues=result.issues,
        regulation_refs=result.regulation_refs,
        document_name=document_name,
        document_type=application_scenario,
        document_type_label=DOCUMENT_TYPE_LABELS.get(application_scenario, application_scenario),
        classification={
            "engineering_type_key": classification.engineering_type_key,
            "contract_type_key": classification.contract_type_key,
            "confidence": classification.confidence,
            "evidence": classification.evidence,
            "source": classification.source,
            "requires_confirmation": classification.requires_confirmation,
        },
        final_engineering_type=record.final_engineering_type,
        final_contract_type=record.final_contract_type,
        classification_confidence=record.classification_confidence,
        rule_package_key=record.rule_package_key,
        rule_package_keys=list(record.rule_package_keys_snapshot or regulation_base.get("rule_package_keys", [])),
        knowledge_sources_snapshot=record.knowledge_sources_snapshot or [],
    )
