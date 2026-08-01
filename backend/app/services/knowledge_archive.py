"""归档招投标资料的删除编排。

任务9 收敛知识库：归档资料（`application_scenario=bidding`）对合同初审检索不可见，
普通用户可在设置页查看自己的归档资料并完整物理删除；系统归档资料仅管理员/迁移脚本可清理。

删除流程覆盖：原文件、Markdown、索引节点、版本和知识库记录，并写审计日志。
失败策略：
- 数据库事务失败 → 回滚，文件未触，文档保持。
- 数据库提交成功但文件删除失败 → 记录 warning，文档已删（孤儿文件可被清理脚本处理）。
- 幂等：再次调用查询不到文档，返回 False，API 层映射为 404。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    DocumentVersion,
    IndexNode,
    KnowledgeDocument,
)
from app.services.file_storage import delete_file

_logger = logging.getLogger(__name__)


class ArchiveDeletionError(RuntimeError):
    """归档删除过程中数据库提交失败，调用方应映射为 5xx。"""


@dataclass(frozen=True)
class ArchivedDocumentView:
    """归档资料只读列表项。"""

    id: int
    title: str
    owner_type: str
    application_scenario: str
    is_active: bool
    created_at: str


def _to_view(document: KnowledgeDocument) -> ArchivedDocumentView:
    return ArchivedDocumentView(
        id=document.id,
        title=document.title,
        owner_type=document.owner_type,
        application_scenario=document.application_scenario,
        is_active=bool(document.is_active),
        created_at=document.created_at.isoformat() if document.created_at else "",
    )


async def list_user_archived_documents(
    db: AsyncSession, user_id: uuid.UUID
) -> list[ArchivedDocumentView]:
    """仅返回当前用户的归档招投标资料；系统归档资料由管理员能力单独处理。"""
    result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.application_scenario == "bidding",
            KnowledgeDocument.owner_type == "user",
            KnowledgeDocument.owner_user_id == user_id,
        )
        .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc())
    )
    documents = list(result.scalars().all())
    return [_to_view(doc) for doc in documents]


def _collect_version_file_paths(versions: list[DocumentVersion]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for version in versions:
        for path in (version.original_file_path, version.markdown_path):
            if not path or path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


async def delete_user_archived_document(
    db: AsyncSession, *, document_id: int, user_id: uuid.UUID
) -> bool:
    """完整删除当前用户的一份归档资料。

    返回 ``True`` 表示文档存在且已被删除；返回 ``False`` 表示文档不存在、非归档
    或不属于当前用户（含系统归档资料），调用方应映射为 404。
    数据库提交失败时抛 :class:`ArchiveDeletionError`，调用方映射为 5xx。
    """
    result = await db.execute(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.application_scenario == "bidding",
            KnowledgeDocument.owner_type == "user",
            KnowledgeDocument.owner_user_id == user_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        return False

    versions_result = await db.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == document_id)
    )
    versions = list(versions_result.scalars().all())
    version_ids = [version.id for version in versions]
    file_paths = _collect_version_file_paths(versions)

    # 显式删除索引节点与版本记录，避免依赖数据库级联配置（任务约束：不改旧迁移）。
    #
    # 删除顺序必须绕开 FK 循环：
    #   knowledge_documents.current_version_id → document_versions.id (NO ACTION)
    #   document_versions.document_id          → knowledge_documents.id (NO ACTION)
    # 若直接删除 DocumentVersion，会被 current_version_id 引用阻止（真实 PostgreSQL
    # 下 100% 触发 ForeignKeyViolationError）。因此：
    #   1. 删 IndexNode（通过 version_id 间接归属 document）
    #   2. 断开 current_version_id 并 flush，使 KnowledgeDocument 不再引用任何版本
    #   3. 删 DocumentVersion（此时已无 KnowledgeDocument 引用）
    #   4. 删 KnowledgeDocument（此时已无 DocumentVersion 引用）
    try:
        if version_ids:
            await db.execute(
                delete(IndexNode).where(IndexNode.version_id.in_(version_ids))
            )
        document.current_version_id = None
        await db.flush()
        if version_ids:
            await db.execute(
                delete(DocumentVersion).where(DocumentVersion.id.in_(version_ids))
            )
        await db.delete(document)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise ArchiveDeletionError("归档资料删除失败") from exc

    # 数据库已提交：清理文件存储为 best-effort，失败不阻塞删除流程（幂等）。
    # delete_file 是同步阻塞 I/O（本地 unlink / OSS 网络请求），放线程池执行避免
    # 阻塞事件循环。
    deleted_files = 0
    missing_files = 0
    for path in file_paths:
        if await asyncio.to_thread(delete_file, path):
            deleted_files += 1
        else:
            missing_files += 1
            _logger.warning(
                "archived_knowledge_file_missing",
                extra={
                    "audit_event": "archived_knowledge_file_missing",
                    "document_id": document_id,
                    "user_id": str(user_id),
                    "storage_path": path,
                },
            )

    _logger.info(
        "archived_knowledge_deleted",
        extra={
            "audit_event": "archived_knowledge_deleted",
            "document_id": document_id,
            "user_id": str(user_id),
            "title": document.title,
            "version_count": len(version_ids),
            "files_deleted": deleted_files,
            "files_missing": missing_files,
        },
    )
    return True
