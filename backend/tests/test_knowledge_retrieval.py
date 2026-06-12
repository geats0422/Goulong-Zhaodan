from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import async_session, engine, init_db  # noqa: E402
from models.knowledge import (  # noqa: E402
    DocumentVersion,
    EngineeringSubcategory,
    IndexNode,
    KnowledgeDocument,
    KnowledgeDocumentSetting,
    User,
)
from services.knowledge_retrieval import retrieve_regulation_base  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    await engine.dispose()
    await init_db()
    assert_safe_database_for_cleanup()
    async with async_session() as session:
        await session.execute(text("UPDATE knowledge_documents SET current_version_id = NULL"))
        for table in [
            "inspection_records",
            "refresh_tokens",
            "api_keys",
            "agent_jobs",
            "knowledge_document_settings",
            "taboo_words",
            "user_profiles",
            "index_nodes",
            "document_versions",
            "knowledge_documents",
            "engineering_subcategories",
            "users",
        ]:
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()
    yield
    await engine.dispose()


async def _create_user(nickname: str = "retrieval_user") -> uuid.UUID:
    async with async_session() as session:
        user = User(nickname=nickname, email=f"{nickname}@test.com", hashed_password="hashed")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def _create_document_with_node(
    *,
    title: str,
    content: str,
    owner_type: str,
    application_scenario: str,
    owner_user_id: uuid.UUID | None = None,
    status: str = "completed",
    position: int = 1,
) -> int:
    async with async_session() as session:
        sub = EngineeringSubcategory(category_key="traditional", name=f"{title}-分类")
        session.add(sub)
        await session.flush()
        doc = KnowledgeDocument(
            title=title,
            subcategory_id=sub.id,
            owner_type=owner_type,
            owner_user_id=owner_user_id,
            application_scenario=application_scenario,
        )
        session.add(doc)
        await session.flush()
        version = DocumentVersion(
            document_id=doc.id,
            version_number=1,
            display_name=f"{title}.md",
            original_file_path=f"/tmp/{title}.md",
            status=status,
            file_size_bytes=len(content),
            file_type=".md",
        )
        session.add(version)
        await session.flush()
        doc.current_version_id = version.id
        session.add(
            IndexNode(
                version_id=version.id,
                node_type="section",
                path_label=f"{title} > 第一条",
                content=content,
                position=position,
            )
        )
        await session.commit()
        return doc.id


@pytest.mark.asyncio
async def test_retrieve_regulation_base_returns_empty_structure():
    user_id = await _create_user()
    async with async_session() as session:
        result = await retrieve_regulation_base(session, user_id=user_id, application_scenario="bidding", limit=5)

    assert result == {"snippets": [], "sources": []}


@pytest.mark.asyncio
async def test_retrieve_regulation_base_returns_only_matching_system_completed_nodes():
    user_id = await _create_user()
    await _create_document_with_node(
        title="招投标法规",
        content="招投标系统法规片段",
        owner_type="system",
        application_scenario="bidding",
    )
    await _create_document_with_node(
        title="合同法规",
        content="合同系统法规片段",
        owner_type="system",
        application_scenario="contract",
    )
    await _create_document_with_node(
        title="未完成法规",
        content="不应返回的片段",
        owner_type="system",
        application_scenario="bidding",
        status="pending",
    )

    async with async_session() as session:
        result = await retrieve_regulation_base(session, user_id=user_id, application_scenario="bidding", limit=10)

    assert [item["content"] for item in result["snippets"]] == ["招投标系统法规片段"]
    assert result["sources"] == [{"document_id": result["snippets"][0]["document_id"], "title": "招投标法规", "owner_type": "system"}]


@pytest.mark.asyncio
async def test_retrieve_regulation_base_excludes_disabled_user_document_and_defaults_enabled():
    user_id = await _create_user()
    # 为"其他用户文档"创建一个不同的用户
    other_user_id = await _create_user("other_retrieval_user")
    disabled_doc_id = await _create_document_with_node(
        title="用户禁用文档",
        content="禁用片段",
        owner_type="user",
        owner_user_id=user_id,
        application_scenario="contract",
    )
    await _create_document_with_node(
        title="用户默认启用文档",
        content="默认启用片段",
        owner_type="user",
        owner_user_id=user_id,
        application_scenario="contract",
    )
    await _create_document_with_node(
        title="其他用户文档",
        content="其他用户片段",
        owner_type="user",
        owner_user_id=other_user_id,
        application_scenario="contract",
    )
    async with async_session() as session:
        session.add(KnowledgeDocumentSetting(user_id=user_id, document_id=disabled_doc_id, enabled=False))
        await session.commit()

    async with async_session() as session:
        result = await retrieve_regulation_base(session, user_id=user_id, application_scenario="contract", limit=10)

    assert [item["content"] for item in result["snippets"]] == ["默认启用片段"]
    assert result["sources"][0]["title"] == "用户默认启用文档"
