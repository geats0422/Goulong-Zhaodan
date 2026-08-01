from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session  # noqa: E402
from app.models.knowledge import (  # noqa: E402
    DocumentVersion,
    EngineeringSubcategory,
    IndexNode,
    KnowledgeDocument,
    KnowledgeDocumentSetting,
)
from goulong_auth.models import User  # noqa: E402
from app.services.knowledge_retrieval import retrieve_regulation_base  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    assert_safe_database_for_cleanup()
    yield


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
    engineering_type_key: str | None = None,
    contract_type_key: str | None = None,
    is_active: bool = True,
    rule_package_key: str | None = None,
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
            engineering_type_key=engineering_type_key,
            contract_type_key=contract_type_key,
            is_active=is_active,
            rule_package_key=rule_package_key,
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
        result = await retrieve_regulation_base(
            session,
            user_id=user_id,
            application_scenario="contract",
            engineering_type_key="municipal-road",
            contract_type_key="professional-subcontract",
            limit=5,
        )

    assert result["snippets"] == []
    assert result["sources"] == []
    assert result["selection_mode"] == "system_fallback"
    assert result["fallback_notice"]


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
        rule_package_key="general-engineering-contract-rules:v1",
    )
    await _create_document_with_node(
        title="未完成法规",
        content="不应返回的片段",
        owner_type="system",
        application_scenario="contract",
        rule_package_key="other-package:v1",
        status="pending",
    )

    async with async_session() as session:
        result = await retrieve_regulation_base(
            session,
            user_id=user_id,
            application_scenario="contract",
            engineering_type_key="general-engineering",
            contract_type_key="other",
            limit=10,
        )

    assert [item["content"] for item in result["snippets"]] == ["合同系统法规片段"]
    assert result["sources"][0]["rule_package_key"] == "general-engineering-contract-rules:v1"


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


@pytest.mark.asyncio
async def test_user_exact_and_generic_matches_win_without_system_mixing():
    user_id = await _create_user()
    await _create_document_with_node(
        title="系统默认规则", content="系统片段", owner_type="system", application_scenario="contract",
        rule_package_key="general-engineering-contract-rules:v1",
    )
    await _create_document_with_node(
        title="用户通用规则", content="用户通用片段", owner_type="user", owner_user_id=user_id,
        application_scenario="contract", engineering_type_key="municipal-road",
    )
    await _create_document_with_node(
        title="用户精确规则", content="用户精确片段", owner_type="user", owner_user_id=user_id,
        application_scenario="contract", engineering_type_key="municipal-road",
        contract_type_key="professional-subcontract",
    )

    async with async_session() as session:
        result = await retrieve_regulation_base(
            session, user_id=user_id, application_scenario="contract",
            engineering_type_key="municipal-road", contract_type_key="professional-subcontract", limit=10,
        )

    assert {item["content"] for item in result["snippets"]} == {"用户通用片段", "用户精确片段"}
    assert result["selection_mode"] == "user"
    assert result["fallback_notice"] is None
    assert all(source["owner_type"] == "user" for source in result["sources"])
    assert result["sources"][0]["contract_type_key"] == "professional-subcontract"


@pytest.mark.asyncio
async def test_no_active_matching_user_document_falls_back_to_active_default_package():
    user_id = await _create_user()
    other_user_id = await _create_user("other_fallback_user")
    await _create_document_with_node(
        title="用户停用规则", content="不应返回", owner_type="user", owner_user_id=user_id,
        application_scenario="contract", engineering_type_key="municipal-road", is_active=False,
    )
    await _create_document_with_node(
        title="其他用户规则", content="不应返回", owner_type="user", owner_user_id=other_user_id,
        application_scenario="contract", engineering_type_key="municipal-road",
    )
    await _create_document_with_node(
        title="默认通用规则", content="应回退", owner_type="system", application_scenario="contract",
        rule_package_key="general-engineering-contract-rules:v1",
    )
    await _create_document_with_node(
        title="停用默认规则", content="不应返回", owner_type="system", application_scenario="contract",
        rule_package_key="general-engineering-contract-rules:v1", is_active=False,
    )

    async with async_session() as session:
        result = await retrieve_regulation_base(
            session, user_id=user_id, application_scenario="contract",
            engineering_type_key="municipal-road", contract_type_key="other", limit=10,
        )

    assert [item["content"] for item in result["snippets"]] == ["应回退"]
    assert result["selection_mode"] == "system_fallback"
    assert result["sources"][0]["rule_package_key"] == "general-engineering-contract-rules:v1"
    assert "回退" in result["fallback_notice"]
