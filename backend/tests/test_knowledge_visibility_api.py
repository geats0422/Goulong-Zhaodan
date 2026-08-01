from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.core.auth import CurrentUserContext
from app.core.database import async_session
from app.api.v1.knowledge import get_document_nodes
from app.models.knowledge import DocumentVersion, EngineeringSubcategory, IndexNode, KnowledgeDocument
from goulong_auth.models import User


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    yield


async def _create_document(*, application_scenario: str, is_active: bool) -> tuple[uuid.UUID, int]:
    async with async_session() as session:
        user = User(
            nickname=f"visibility-{uuid.uuid4().hex[:8]}",
            email=f"visibility-{uuid.uuid4().hex}@test.com",
            hashed_password="hashed",
        )
        session.add(user)
        subcategory = EngineeringSubcategory(category_key="traditional", name=f"分类-{uuid.uuid4().hex[:8]}")
        session.add(subcategory)
        await session.flush()
        document = KnowledgeDocument(
            title="可见性测试文档",
            subcategory_id=subcategory.id,
            owner_type="user",
            owner_user_id=user.id,
            application_scenario=application_scenario,
            is_active=is_active,
        )
        session.add(document)
        await session.flush()
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            display_name="visibility.md",
            original_file_path=f"/tmp/{document.id}.md",
            status="completed",
            file_size_bytes=4,
            file_type=".md",
        )
        session.add(version)
        await session.flush()
        document.current_version_id = version.id
        session.add(
            IndexNode(
                version_id=version.id,
                node_type="section",
                path_label="第一条",
                content="内容",
                position=1,
            )
        )
        await session.commit()
        return user.id, document.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application_scenario", "is_active"),
    [("bidding", True), ("contract", False)],
)
async def test_document_nodes_apply_database_visibility_filters(
    application_scenario: str, is_active: bool,
) -> None:
    user_id, document_id = await _create_document(
        application_scenario=application_scenario,
        is_active=is_active,
    )

    async with async_session() as session:
        with pytest.raises(HTTPException) as error:
            await get_document_nodes(
                document_id=document_id,
                db=session,
                user=CurrentUserContext(user_id=user_id),
            )

    assert error.value.status_code == 404
