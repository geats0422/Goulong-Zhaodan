from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, patch

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

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.api_keys import ApiKey
from goulong_auth.models import User

from app.services.agent_job_service import (
    create_job,
    get_job,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
    update_job_status,
)


@pytest_asyncio.fixture
async def engine():
    from app.core.database import engine as global_engine
    yield global_engine


@pytest_asyncio.fixture
def async_session_factory(engine):
    from app.core.database import async_session
    return async_session


@pytest_asyncio.fixture
async def session(async_session_factory):
    async with async_session_factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def user_id(session: AsyncSession) -> int:
    user = User(nickname="job_tester", email="job_tester@test.com", hashed_password="fakehash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


@pytest_asyncio.fixture
async def other_user_id(session: AsyncSession) -> int:
    user = User(nickname="other_user", email="other_user@test.com", hashed_password="fakehash")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


@pytest_asyncio.fixture
async def api_key_id(session: AsyncSession, user_id: int) -> int:
    key = ApiKey(
        user_id=user_id,
        name="Service Test Key",
        client_type="agent",
        scope_template="agent_automation",
        scopes=["agent:run"],
        key_prefix="gou_svc",
        key_hash="hash_svc",
        encrypted_key="enc_svc",
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key.id


@pytest.mark.asyncio
async def test_create_inspect_job(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        job = await create_job(session, user_id, api_key_id, "inspect")

    assert job is not None
    assert job.job_id.startswith("job_")
    assert job.job_type == "inspect"
    assert job.status == "queued"
    assert job.progress == 0
    assert job.user_id == user_id
    assert job.api_key_id == api_key_id


@pytest.mark.asyncio
async def test_create_parse_job(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        job = await create_job(session, user_id, api_key_id, "parse")

    assert job.job_type == "parse"
    assert job.status == "queued"


@pytest.mark.asyncio
async def test_create_knowledge_upload_job(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        job = await create_job(
            session, user_id, api_key_id, "knowledge_upload"
        )

    assert job.job_type == "knowledge_upload"
    assert job.status == "queued"


@pytest.mark.asyncio
async def test_create_job_with_payload(
    session: AsyncSession, user_id: int, api_key_id: int
):
    payload = {"document_id": 42, "options": {"deep_scan": True}}
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        job = await create_job(
            session, user_id, api_key_id, "inspect", input_payload=payload
        )

    assert job.input_payload == payload


@pytest.mark.asyncio
async def test_get_job_by_job_id(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        created = await create_job(session, user_id, api_key_id, "inspect")

    found = await get_job(session, created.job_id, user_id)

    assert found is not None
    assert found.job_id == created.job_id
    assert found.user_id == user_id


@pytest.mark.asyncio
async def test_get_job_user_isolation(
    session: AsyncSession,
    user_id: int,
    other_user_id: int,
    api_key_id: int,
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        created = await create_job(session, user_id, api_key_id, "inspect")

    found = await get_job(session, created.job_id, other_user_id)

    assert found is None


@pytest.mark.asyncio
async def test_update_job_status(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        created = await create_job(session, user_id, api_key_id, "inspect")

    updated = await update_job_status(
        session,
        created.job_id,
        status="processing",
        progress=30,
        message="正在处理",
    )

    assert updated is not None
    assert updated.status == "processing"
    assert updated.progress == 30
    assert updated.message == "正在处理"


@pytest.mark.asyncio
async def test_mark_job_running(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        created = await create_job(session, user_id, api_key_id, "inspect")

    updated = await mark_job_running(session, created.job_id)

    assert updated is not None
    assert updated.status == "running"


@pytest.mark.asyncio
async def test_mark_job_succeeded(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        created = await create_job(session, user_id, api_key_id, "inspect")

    result = {"risk_level": "low", "issues": []}
    updated = await mark_job_succeeded(session, created.job_id, result_payload=result)

    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.result_payload == result
    assert updated.finished_at is not None


@pytest.mark.asyncio
async def test_mark_job_failed(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch("app.services.agent_job_service.enqueue_job", new_callable=AsyncMock):
        created = await create_job(session, user_id, api_key_id, "inspect")

    updated = await mark_job_failed(
        session, created.job_id, error_message="文档解析超时"
    )

    assert updated is not None
    assert updated.status == "failed"
    assert updated.error_message == "文档解析超时"
    assert updated.finished_at is not None


@pytest.mark.asyncio
async def test_create_job_enqueue_failure(
    session: AsyncSession, user_id: int, api_key_id: int
):
    with patch(
        "app.services.agent_job_service.enqueue_job",
        new_callable=AsyncMock,
        side_effect=Exception("Redis connection refused"),
    ):
        job = await create_job(session, user_id, api_key_id, "inspect")

    assert job is not None
    assert job.status == "queued"
    assert job.job_id.startswith("job_")

    found = await get_job(session, job.job_id, user_id)
    assert found is not None
