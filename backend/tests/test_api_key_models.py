from __future__ import annotations

import sys
import types
from pathlib import Path

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

import datetime  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from goulong_auth.models import User  # noqa: E402
from app.models.api_keys import AgentJob, ApiKey  # noqa: E402


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
    user = User(
        nickname="apikey_tester",
        email="apikey_tester@test.com",
        hashed_password="fakehash",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user.id


@pytest.mark.asyncio
async def test_tables_created(engine):
    from sqlalchemy import text
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'zhaodan' ORDER BY table_name"
            )
        )
        table_names = {row[0] for row in result.fetchall()}
    assert "api_keys" in table_names
    assert "agent_jobs" in table_names


@pytest.mark.asyncio
async def test_api_key_default_status_active(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="测试 Key",
        client_type="mcp",
        scope_template="mcp_readonly",
        scopes=["read:documents"],
        key_prefix="gou_abc",
        key_hash="sha256hash",
        encrypted_key="enc_value",
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    assert api_key.status == "active"
    assert api_key.id is not None
    assert api_key.user_id == user_id
    assert api_key.name == "测试 Key"
    assert api_key.client_type == "mcp"
    assert api_key.scope_template == "mcp_readonly"
    assert api_key.key_prefix == "gou_abc"
    assert api_key.key_hash == "sha256hash"
    assert api_key.encrypted_key == "enc_value"


@pytest.mark.asyncio
async def test_api_key_scopes_json_read_write(session: AsyncSession, user_id: int):
    scopes = ["read:documents", "write:documents", "inspect:files"]
    api_key = ApiKey(
        user_id=user_id,
        name="JSON 测试",
        client_type="agent",
        scope_template="custom",
        scopes=scopes,
        key_prefix="gou_xyz",
        key_hash="hash123",
        encrypted_key="enc_xyz",
    )
    session.add(api_key)
    await session.commit()

    result = await session.get(ApiKey, api_key.id)
    assert result.scopes == scopes


@pytest.mark.asyncio
async def test_api_key_timestamps_auto_filled(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="时间测试",
        client_type="cli",
        scope_template="cli_inspection",
        scopes=[],
        key_prefix="gou_ts",
        key_hash="hash_ts",
        encrypted_key="enc_ts",
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    assert api_key.created_at is not None
    assert isinstance(api_key.created_at, datetime.datetime)
    assert api_key.updated_at is not None
    assert isinstance(api_key.updated_at, datetime.datetime)


@pytest.mark.asyncio
async def test_api_key_expires_at_nullable(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="永不过期",
        client_type="skill",
        scope_template="custom",
        scopes=["read"],
        key_prefix="gou_ne",
        key_hash="hash_ne",
        encrypted_key="enc_ne",
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    assert api_key.expires_at is None


@pytest.mark.asyncio
async def test_api_key_revoked_status(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="已撤销",
        client_type="mcp",
        scope_template="mcp_readonly",
        scopes=["read"],
        key_prefix="gou_rev",
        key_hash="hash_rev",
        encrypted_key="enc_rev",
        status="revoked",
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    assert api_key.status == "revoked"


@pytest.mark.asyncio
async def test_agent_job_default_status_queued(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="Job 所属 Key",
        client_type="agent",
        scope_template="agent_automation",
        scopes=["agent:run"],
        key_prefix="gou_job",
        key_hash="hash_job",
        encrypted_key="enc_job",
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    job = AgentJob(
        job_id="job_abc123",
        user_id=user_id,
        api_key_id=api_key.id,
        job_type="inspect",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    assert job.status == "queued"
    assert job.progress == 0
    assert job.id is not None
    assert job.user_id == user_id
    assert job.api_key_id == api_key.id
    assert job.job_type == "inspect"


@pytest.mark.asyncio
async def test_agent_job_id_prefix(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="前缀测试",
        client_type="agent",
        scope_template="agent_automation",
        scopes=["agent:run"],
        key_prefix="gou_pf",
        key_hash="hash_pf",
        encrypted_key="enc_pf",
    )
    session.add(api_key)
    await session.commit()

    job = AgentJob(
        job_id="job_xyz789",
        user_id=user_id,
        api_key_id=api_key.id,
        job_type="parse",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    assert job.job_id.startswith("job_")


@pytest.mark.asyncio
async def test_agent_job_json_payload_read_write(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="Payload 测试",
        client_type="agent",
        scope_template="agent_automation",
        scopes=["agent:run"],
        key_prefix="gou_pl",
        key_hash="hash_pl",
        encrypted_key="enc_pl",
    )
    session.add(api_key)
    await session.commit()

    input_payload = {"document_id": 42, "options": {"deep_scan": True}}
    result_payload = {"risk_level": "high", "issues_count": 3}

    job = AgentJob(
        job_id="job_payload_001",
        user_id=user_id,
        api_key_id=api_key.id,
        job_type="knowledge_upload",
        input_payload=input_payload,
        result_payload=result_payload,
    )
    session.add(job)
    await session.commit()

    loaded = await session.get(AgentJob, job.id)
    assert loaded.input_payload == input_payload
    assert loaded.result_payload == result_payload


@pytest.mark.asyncio
async def test_agent_job_timestamps(session: AsyncSession, user_id: int):
    api_key = ApiKey(
        user_id=user_id,
        name="时间戳测试",
        client_type="agent",
        scope_template="agent_automation",
        scopes=["agent:run"],
        key_prefix="gou_tt",
        key_hash="hash_tt",
        encrypted_key="enc_tt",
    )
    session.add(api_key)
    await session.commit()

    job = AgentJob(
        job_id="job_ts_001",
        user_id=user_id,
        api_key_id=api_key.id,
        job_type="inspect",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    assert job.created_at is not None
    assert isinstance(job.created_at, datetime.datetime)
    assert job.updated_at is not None
    assert isinstance(job.updated_at, datetime.datetime)
    assert job.finished_at is None


@pytest.mark.asyncio
async def test_agent_job_relationship_with_api_key(
    session: AsyncSession, user_id: int
):
    api_key = ApiKey(
        user_id=user_id,
        name="关系测试",
        client_type="agent",
        scope_template="agent_automation",
        scopes=["agent:run"],
        key_prefix="gou_rel",
        key_hash="hash_rel",
        encrypted_key="enc_rel",
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    job = AgentJob(
        job_id="job_rel_001",
        user_id=user_id,
        api_key_id=api_key.id,
        job_type="inspect",
        status="running",
        progress=50,
        message="正在解析文档...",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    assert job.api_key_id == api_key.id
    assert job.status == "running"
    assert job.progress == 50
    assert job.message == "正在解析文档..."

    loaded_key = await session.get(ApiKey, api_key.id)
    assert loaded_key is not None
    assert loaded_key.id == job.api_key_id


@pytest.mark.asyncio
async def test_api_key_multiple_for_same_user(session: AsyncSession, user_id: int):
    keys = []
    for i in range(3):
        key = ApiKey(
            user_id=user_id,
            name=f"Key {i}",
            client_type="mcp",
            scope_template="mcp_readonly",
            scopes=["read"],
            key_prefix=f"gou_m{i}",
            key_hash=f"hash_m{i}",
            encrypted_key=f"enc_m{i}",
        )
        session.add(key)
        keys.append(key)
    await session.commit()

    for key in keys:
        await session.refresh(key)

    key_ids = [k.id for k in keys]
    assert len(set(key_ids)) == 3

    for key in keys:
        assert key.user_id == user_id
        assert key.status == "active"
