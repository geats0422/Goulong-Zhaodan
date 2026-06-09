from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge import DocumentVersion, IndexNode, KnowledgeDocument, KnowledgeDocumentSetting


async def retrieve_regulation_base(
    db: AsyncSession,
    user_id: int,
    application_scenario: str,
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    stmt = (
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
            KnowledgeDocument.application_scenario == application_scenario,
            DocumentVersion.status == "completed",
            IndexNode.content.is_not(None),
            or_(
                KnowledgeDocument.owner_type == "system",
                and_(
                    KnowledgeDocument.owner_type == "user",
                    KnowledgeDocument.owner_user_id == user_id,
                    or_(KnowledgeDocumentSetting.id.is_(None), KnowledgeDocumentSetting.enabled.is_(True)),
                ),
            ),
        )
        .order_by(KnowledgeDocument.created_at, IndexNode.position)
        .limit(limit)
    )

    rows = (await db.execute(stmt)).all()
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
            {"document_id": doc.id, "title": doc.title, "owner_type": doc.owner_type},
        )

    return {"snippets": snippets, "sources": list(sources_by_id.values())}
