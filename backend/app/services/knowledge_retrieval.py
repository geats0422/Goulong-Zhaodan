from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import DocumentVersion, IndexNode, KnowledgeDocument, KnowledgeDocumentSetting

DEFAULT_RULE_PACKAGE_KEY = "general-engineering-contract-rules:v1"
DEFAULT_ENGINEERING_TYPE_KEY = "general-engineering"
DEFAULT_CONTRACT_TYPE_KEY = "other"
FALLBACK_NOTICE = "未找到当前用户已启用的匹配知识库，已回退系统默认通用工程合同规则包"


def _binding_filter(column, key: str | None):
    return column.is_(None) if key is None else or_(column == key, column.is_(None))


def _match_rank(engineering_type_key: str | None, contract_type_key: str | None):
    exact = and_(
        KnowledgeDocument.engineering_type_key == engineering_type_key,
        KnowledgeDocument.contract_type_key == contract_type_key,
    )
    engineering_only = and_(
        KnowledgeDocument.engineering_type_key == engineering_type_key,
        KnowledgeDocument.contract_type_key.is_(None),
    )
    contract_only = and_(
        KnowledgeDocument.engineering_type_key.is_(None),
        KnowledgeDocument.contract_type_key == contract_type_key,
    )
    return case((exact, 4), (engineering_only, 3), (contract_only, 2), else_=1)


def _base_statement(*, user_id: uuid.UUID, engineering_type_key: str, contract_type_key: str):
    return (
        select(KnowledgeDocument, IndexNode)
        .join(DocumentVersion, KnowledgeDocument.current_version_id == DocumentVersion.id)
        .join(IndexNode, IndexNode.version_id == DocumentVersion.id)
        .outerjoin(
            KnowledgeDocumentSetting,
            and_(
                KnowledgeDocumentSetting.document_id == KnowledgeDocument.id,
                KnowledgeDocumentSetting.user_id == user_id,
            ),
        )
        .where(
            KnowledgeDocument.application_scenario == "contract",
            KnowledgeDocument.is_active.is_(True),
            DocumentVersion.status == "completed",
            IndexNode.content.is_not(None),
            _binding_filter(KnowledgeDocument.engineering_type_key, engineering_type_key),
            _binding_filter(KnowledgeDocument.contract_type_key, contract_type_key),
        )
    )


def _to_result(rows: list[tuple[KnowledgeDocument, IndexNode]], selection_mode: str, fallback_notice: str | None):
    snippets: list[dict[str, Any]] = []
    sources_by_id: dict[int, dict[str, Any]] = {}
    for doc, node in rows:
        snippets.append(
            {
                "document_id": doc.id,
                "title": doc.title,
                "owner_type": doc.owner_type,
                "path_label": node.path_label,
                "content": node.content or "",
            }
        )
        sources_by_id.setdefault(
            doc.id,
            {
                "document_id": doc.id,
                "title": doc.title,
                "owner_type": doc.owner_type,
                "rule_package_key": (
                    doc.rule_package_key
                    or (DEFAULT_RULE_PACKAGE_KEY if selection_mode == "system_fallback" else None)
                ),
                "engineering_type_key": doc.engineering_type_key,
                "contract_type_key": doc.contract_type_key,
            },
        )
    return {
        "snippets": snippets,
        "sources": list(sources_by_id.values()),
        "selection_mode": selection_mode,
        "fallback_notice": fallback_notice,
    }


async def retrieve_regulation_base(
    db: AsyncSession,
    user_id: uuid.UUID,
    application_scenario: str,
    limit: int,
    engineering_type_key: str | None = None,
    contract_type_key: str | None = None,
) -> dict[str, Any]:
    """按用户优先策略召回合同规则，系统规则只在用户无匹配时回退。"""
    if application_scenario != "contract":
        return _to_result([], "system_fallback", FALLBACK_NOTICE)

    engineering_type_key = engineering_type_key or DEFAULT_ENGINEERING_TYPE_KEY
    contract_type_key = contract_type_key or DEFAULT_CONTRACT_TYPE_KEY
    user_stmt = (
        _base_statement(
            user_id=user_id,
            engineering_type_key=engineering_type_key,
            contract_type_key=contract_type_key,
        )
        .where(
            KnowledgeDocument.owner_type == "user",
            KnowledgeDocument.owner_user_id == user_id,
            or_(KnowledgeDocumentSetting.id.is_(None), KnowledgeDocumentSetting.enabled.is_(True)),
        )
        .order_by(_match_rank(engineering_type_key, contract_type_key).desc(), KnowledgeDocument.created_at, IndexNode.position)
        .limit(limit)
    )
    user_rows = list((await db.execute(user_stmt)).all())
    if user_rows:
        return _to_result(user_rows, "user", None)

    system_stmt = (
        _base_statement(
            user_id=user_id,
            engineering_type_key=engineering_type_key,
            contract_type_key=contract_type_key,
        )
        .where(
            KnowledgeDocument.owner_type == "system",
            or_(
                KnowledgeDocument.rule_package_key == DEFAULT_RULE_PACKAGE_KEY,
                KnowledgeDocument.rule_package_key.is_(None),
            ),
        )
        .order_by(_match_rank(engineering_type_key, contract_type_key).desc(), KnowledgeDocument.created_at, IndexNode.position)
        .limit(limit)
    )
    system_rows = list((await db.execute(system_stmt)).all())
    return _to_result(system_rows, "system_fallback", FALLBACK_NOTICE)
