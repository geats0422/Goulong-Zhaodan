"""体检执行核心 — 从 router 层下沉的业务逻辑（多 Agent 审查流水线）。

inspection.py 与 agent.py 共同引用；workers/tasks.py 的异步 runner 也复用，
避免跨进程 import router 模块。
"""
from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.inspector import run_inspection
from app.core.data_encryption import encrypt_text
from app.core.deps import InspectionDeps
from app.models.knowledge import InspectionRecord, TabooWord
from goulong_auth.models import Membership
from app.services.knowledge_retrieval import retrieve_regulation_base

_logger = logging.getLogger(__name__)

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


# 内存中的体检记录缓存（后续可替换为 PostgreSQL）
_inspection_records: list[dict[str, Any]] = []


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


def inspection_record_to_history_dict(record: InspectionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "user_id": record.user_id,
        "document_name": record.document_name,
        "project_id": record.project_id,
        "overall_risk": record.overall_risk,
        "summary": record.summary,
        "issues": record.issues or [],
        "regulation_refs": record.regulation_refs or [],
        "text_preview": record.text_preview,
        "created_at": record.created_at,
        "quota_consumed": record.quota_consumed,
    }


def append_history_record(record: InspectionRecord) -> None:
    """更新内存缓存：去重后追加（供历史统计读取）。"""
    _inspection_records[:] = [r for r in _inspection_records if r.get("id") != record.id]
    _inspection_records.append(inspection_record_to_history_dict(record))


async def add_pending_inspection_record(
    *,
    db: AsyncSession,
    user_id: uuid.UUID,
    document_name: str,
    document_type: str,
    document_type_label: str,
    text: str,
    project_id: str = "default",
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
        overall_risk="pending",
        summary="文件已解析，等待审查",
        issues=[],
        regulation_refs=[],
        text_preview=text[:500],
        parsed_content=encrypt_text(text),
        quota_consumed=0,
    )
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
) -> InspectionRecord:
    """落库一条 pending 记录（已解析、待审查），并更新内存缓存。"""
    record = await add_pending_inspection_record(
        db=db,
        user_id=user_id,
        document_name=document_name,
        document_type=document_type,
        document_type_label=document_type_label,
        text=text,
        project_id=project_id,
    )
    await db.commit()
    await db.refresh(record)
    append_history_record(record)
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
) -> InspectionReportResponse:
    """公共审查执行：加载违禁词 → 召回知识库 → 运行 Agent → 保存记录 → 返回报告。"""

    # ── 额度检查：体检前校验剩余配额和订阅有效期 ──
    result_mem = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.product == "zhaodan",
            Membership.status == "active",
        )
    )
    membership = result_mem.scalar_one_or_none()
    if membership is not None:
        if (membership.token_used or 0) >= (membership.token_quota or 0):
            raise HTTPException(status_code=403, detail="额度已用完，请购买额度包或升级订阅")
        if membership.expires_at is not None:
            now_naive = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            expires = membership.expires_at
            if hasattr(expires, "tzinfo") and expires.tzinfo is not None:
                expires = expires.replace(tzinfo=None)
            if expires < now_naive:
                raise HTTPException(status_code=403, detail="订阅已过期，请续费")

    saved_taboo_words = await load_user_taboo_words(db, user_id)
    temporary_taboo_words = [w.strip() for w in taboo_words_input.split(",") if w.strip()]
    taboo_list = merge_unique_words(saved_taboo_words, temporary_taboo_words)
    regulation_base = await retrieve_regulation_base(
        db,
        user_id=user_id,
        application_scenario=application_scenario,
        limit=8,
    )

    deps = InspectionDeps(
        project_id=project_id,
        user_id=str(user_id),
        application_scenario=application_scenario,
        regulation_base=regulation_base,
        taboo_words=taboo_list or None,
        db=db,
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
    record.overall_risk = result.overall_risk
    record.summary = result.summary
    record.issues = result.issues
    record.regulation_refs = result.regulation_refs
    record.text_preview = text[:500]
    record.parsed_content = encrypt_text(text)
    record.quota_consumed = max(1, len(text) // 500)

    # ── 扣减用户配额 ──
    if membership is not None:
        membership.token_used = (membership.token_used or 0) + record.quota_consumed

    await db.commit()
    await db.refresh(record)
    append_history_record(record)

    return InspectionReportResponse(
        id=record.id,
        overall_risk=result.overall_risk,
        summary=result.summary,
        issues=result.issues,
        regulation_refs=result.regulation_refs,
        document_name=document_name,
        document_type=application_scenario,
        document_type_label=DOCUMENT_TYPE_LABELS.get(application_scenario, application_scenario),
    )
