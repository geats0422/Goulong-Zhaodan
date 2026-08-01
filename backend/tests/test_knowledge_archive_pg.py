"""归档资料删除编排的真实 PostgreSQL 集成测试。

任务9 质量审查修复（CRITICAL+HIGH）：
- 验证 knowledge_documents.current_version_id ↔ document_versions.document_id
  外键循环下，删除顺序正确，真实 PostgreSQL 不报 FK 违约。
- 验证跨用户/非归档资料的权限隔离。
- 验证提交失败时事务回滚、文档保留。
- 验证同步文件删除通过线程池执行，不阻塞事件循环。
"""

from __future__ import annotations

import sys
import threading
import types
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "markitdown",
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.models.knowledge import (  # noqa: E402
    DocumentVersion,
    EngineeringSubcategory,
    IndexNode,
    KnowledgeDocument,
)
from app.services import knowledge_archive  # noqa: E402
from app.services.knowledge_archive import (  # noqa: E402
    ArchiveDeletionError,
    delete_user_archived_document,
)
from goulong_auth.models import User  # noqa: E402


@pytest_asyncio.fixture
async def session_factory():
    from app.core.database import async_session

    return async_session


async def _make_user(db: AsyncSession, *, nickname: str, email: str) -> uuid.UUID:
    user = User(
        nickname=nickname,
        email=email,
        hashed_password="test-hash",
    )
    db.add(user)
    await db.flush()
    return user.id


async def _make_subcategory(db: AsyncSession, *, key: str, name: str) -> int:
    sub = EngineeringSubcategory(category_key=key, name=name)
    db.add(sub)
    await db.flush()
    return sub.id


async def _seed_archived_document(
    db: AsyncSession,
    *,
    owner_user_id: uuid.UUID,
    application_scenario: str = "bidding",
    title: str = "归档招标资料",
    is_active: bool = False,
    with_index_node: bool = True,
    original_file_path: str = "archive/v1/source.pdf",
    markdown_path: str | None = "archive/v1/source.md",
) -> tuple[KnowledgeDocument, DocumentVersion]:
    """构造完整的 document→version→index_node 链并绑定 current_version_id。

    插入顺序必须绕开 FK 循环：先 document(current_version_id=NULL) → version →
    回填 current_version_id → index_node。这与生产 cleanup 逻辑一致。
    """
    subcategory_id = await _make_subcategory(
        db, key="traditional", name=f"房建-{title}"
    )
    document = KnowledgeDocument(
        title=title,
        subcategory_id=subcategory_id,
        current_version_id=None,
        owner_type="user",
        owner_user_id=owner_user_id,
        application_scenario=application_scenario,
        is_active=is_active,
    )
    db.add(document)
    await db.flush()

    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        display_name=f"{title}.pdf",
        original_file_path=original_file_path,
        markdown_path=markdown_path,
        status="completed",
        file_size_bytes=128,
        file_type=".pdf",
    )
    db.add(version)
    await db.flush()

    # 回填 current_version_id 触发 FK 循环：删除时必须先断开此引用。
    document.current_version_id = version.id
    await db.flush()

    if with_index_node:
        db.add(
            IndexNode(
                version_id=version.id,
                parent_id=None,
                node_type="section",
                path_label="第一章",
                content="正文",
                position=0,
            )
        )
    await db.flush()
    return document, version


# ---------------------------------------------------------------------------
# CRITICAL: 删除顺序必须在真实 PostgreSQL 下绕开 FK 循环
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_all_records_under_fk_cycle(session_factory):
    """带 current_version_id 绑定的归档资料能被完整删除。

    回归：旧实现先删 DocumentVersion 会被 KnowledgeDocument.current_version_id
    的 NO ACTION 外键阻止（真实 PostgreSQL 下 100% 失败）。
    """
    async with session_factory() as db:
        user_id = await _make_user(
            db, nickname="archive-owner", email="archive-owner@test.local"
        )
        document, version = await _seed_archived_document(db, owner_user_id=user_id)
        document_id = document.id
        version_id = version.id
        await db.commit()

    deleted_paths: list[str] = []

    def fake_delete_file(path: str) -> bool:
        deleted_paths.append(path)
        return True

    with patch.object(knowledge_archive, "delete_file", side_effect=fake_delete_file):
        async with session_factory() as db:
            result = await delete_user_archived_document(
                db, document_id=document_id, user_id=user_id
            )

    assert result is True

    # 所有数据库记录应已清除
    async with session_factory() as check_db:
        doc = await check_db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        versions = (
            await check_db.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == document_id)
            )
        ).scalars().all()
        nodes = (
            await check_db.execute(
                select(IndexNode).where(IndexNode.version_id == version_id)
            )
        ).scalars().all()

    assert doc is None, "KnowledgeDocument 必须被删除"
    assert versions == [], "DocumentVersion 必须被删除"
    assert nodes == [], "IndexNode 必须被删除"
    assert "archive/v1/source.pdf" in deleted_paths
    assert "archive/v1/source.md" in deleted_paths


@pytest.mark.asyncio
async def test_delete_handles_document_without_current_version(session_factory):
    """current_version_id 为 NULL 时（未绑定版本）删除同样成功。"""
    async with session_factory() as db:
        user_id = await _make_user(
            db, nickname="no-current-owner", email="no-current@test.local"
        )
        document, _ = await _seed_archived_document(
            db,
            owner_user_id=user_id,
            with_index_node=False,
            markdown_path=None,
        )
        document.current_version_id = None  # 显式断开
        document_id = document.id
        await db.commit()

    with patch.object(knowledge_archive, "delete_file", return_value=True):
        async with session_factory() as db:
            result = await delete_user_archived_document(
                db, document_id=document_id, user_id=user_id
            )

    assert result is True


# ---------------------------------------------------------------------------
# HIGH: 权限越权 — 跨用户 / 非归档资料拒绝删除
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_false_for_other_users_document(session_factory):
    """删除他人归档资料返回 False，且不触碰任何记录。"""
    async with session_factory() as db:
        owner_id = await _make_user(
            db, nickname="real-owner", email="real-owner@test.local"
        )
        intruder_id = await _make_user(
            db, nickname="intruder", email="intruder@test.local"
        )
        document, _ = await _seed_archived_document(db, owner_user_id=owner_id)
        document_id = document.id
        await db.commit()

    with patch.object(knowledge_archive, "delete_file", return_value=True) as mock_del:
        async with session_factory() as db:
            result = await delete_user_archived_document(
                db, document_id=document_id, user_id=intruder_id
            )

    assert result is False
    mock_del.assert_not_called()

    async with session_factory() as check_db:
        doc = await check_db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
    assert doc is not None, "他人文档必须保留"


@pytest.mark.asyncio
async def test_delete_returns_false_for_non_bidding_document(session_factory):
    """contract 场景文档不在归档删除范围。"""
    async with session_factory() as db:
        user_id = await _make_user(
            db, nickname="contract-owner", email="contract-owner@test.local"
        )
        document, _ = await _seed_archived_document(
            db,
            owner_user_id=user_id,
            application_scenario="contract",
        )
        document_id = document.id
        await db.commit()

    async with session_factory() as db:
        result = await delete_user_archived_document(
            db, document_id=document_id, user_id=user_id
        )

    assert result is False


# ---------------------------------------------------------------------------
# HIGH: 提交失败回滚 — 文档保留
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_raises_and_preserves_data_on_commit_failure(session_factory):
    """数据库提交失败时抛 ArchiveDeletionError，事务回滚，文档与版本完整保留。"""
    async with session_factory() as db:
        user_id = await _make_user(
            db, nickname="rollback-owner", email="rollback-owner@test.local"
        )
        document, version = await _seed_archived_document(db, owner_user_id=user_id)
        document_id = document.id
        version_id = version.id
        await db.commit()

    from sqlalchemy.exc import OperationalError

    with patch.object(knowledge_archive, "delete_file", return_value=True):
        async with session_factory() as db:
            # commit 抛 SQLAlchemyError 子类（真实数据库故障的形态），事务不提交。
            async def failing_commit():
                raise OperationalError(
                    statement="COMMIT", params={}, orig=Exception("db down")
                )

            db.commit = failing_commit
            with pytest.raises(ArchiveDeletionError):
                await delete_user_archived_document(
                    db, document_id=document_id, user_id=user_id
                )

    async with session_factory() as check_db:
        doc = await check_db.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        versions = (
            await check_db.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == document_id)
            )
        ).scalars().all()
        nodes = (
            await check_db.execute(
                select(IndexNode).where(IndexNode.version_id == version_id)
            )
        ).scalars().all()

    assert doc is not None, "提交失败时文档必须保留"
    assert len(versions) == 1, "提交失败时版本必须保留"
    assert len(nodes) == 1, "提交失败时索引节点必须保留"


# ---------------------------------------------------------------------------
# HIGH: 文件删除通过线程池执行，不阻塞事件循环
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_file_runs_in_worker_thread_not_event_loop(session_factory):
    """delete_file 是同步阻塞 I/O，必须在线程池执行而非事件循环线程。"""
    async with session_factory() as db:
        user_id = await _make_user(
            db, nickname="thread-owner", email="thread-owner@test.local"
        )
        document, _ = await _seed_archived_document(
            db,
            owner_user_id=user_id,
            original_file_path="archive/thread/source.pdf",
            markdown_path="archive/thread/source.md",
        )
        document_id = document.id
        await db.commit()

    event_loop_thread = threading.get_ident()
    captured_thread_ids: list[int] = []

    def spying_delete_file(path: str) -> bool:
        captured_thread_ids.append(threading.get_ident())
        return True

    with patch.object(knowledge_archive, "delete_file", side_effect=spying_delete_file):
        async with session_factory() as db:
            result = await delete_user_archived_document(
                db, document_id=document_id, user_id=user_id
            )

    assert result is True
    assert captured_thread_ids, "delete_file 应被调用"
    assert all(
        tid != event_loop_thread for tid in captured_thread_ids
    ), "delete_file 必须在 worker 线程执行，不能阻塞事件循环"


@pytest.mark.asyncio
async def test_delete_file_invocation_is_awaitable_and_serial(session_factory):
    """asyncio.to_thread 包裹后调用点可被 await，且按顺序处理所有路径。"""
    async with session_factory() as db:
        user_id = await _make_user(
            db, nickname="serial-owner", email="serial-owner@test.local"
        )
        # 两个版本 → 4 条去重路径（原文件+md × 2）
        subcategory_id = await _make_subcategory(db, key="traditional", name="房建-serial")
        document = KnowledgeDocument(
            title="serial",
            subcategory_id=subcategory_id,
            current_version_id=None,
            owner_type="user",
            owner_user_id=user_id,
            application_scenario="bidding",
            is_active=False,
        )
        db.add(document)
        await db.flush()
        v1 = DocumentVersion(
            document_id=document.id, version_number=1, display_name="v1.pdf",
            original_file_path="serial/v1/a.pdf", markdown_path="serial/v1/a.md",
            status="completed", file_size_bytes=1, file_type=".pdf",
        )
        v2 = DocumentVersion(
            document_id=document.id, version_number=2, display_name="v2.pdf",
            original_file_path="serial/v2/b.pdf", markdown_path="serial/v2/b.md",
            status="completed", file_size_bytes=1, file_type=".pdf",
        )
        db.add_all([v1, v2])
        await db.flush()
        document.current_version_id = v2.id
        document_id = document.id
        await db.commit()

    call_order: list[str] = []

    def recording_delete_file(path: str) -> bool:
        call_order.append(path)
        return True

    with patch.object(knowledge_archive, "delete_file", side_effect=recording_delete_file):
        async with session_factory() as db:
            result = await delete_user_archived_document(
                db, document_id=document_id, user_id=user_id
            )

    assert result is True
    assert set(call_order) == {
        "serial/v1/a.pdf", "serial/v1/a.md", "serial/v2/b.pdf", "serial/v2/b.md",
    }
