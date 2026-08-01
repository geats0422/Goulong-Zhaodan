from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in ["pageindex", "pydantic_ai", "pydantic_ai.agent", "pydantic_ai.models"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
sys.modules["pydantic_ai"].Agent = MagicMock()
if "markitdown" not in sys.modules:
    fake_markitdown = types.ModuleType("markitdown")
    fake_markitdown.MarkItDown = MagicMock()
    sys.modules["markitdown"] = fake_markitdown

from app.core.database import async_session  # noqa: E402
from app.models.knowledge import InspectionRecord, InspectionType  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture
async def client(monkeypatch):
    from app.core.rate_limit import register_limiter
    from app.services import email_service

    register_limiter.reset()
    monkeypatch.setattr(email_service, "verify_code", AsyncMock(return_value=True))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture(autouse=True)
async def cleanup_inspection_types():
    yield
    async with async_session() as db:
        await db.execute(InspectionType.__table__.delete())
        await db.commit()


async def register(client: AsyncClient, name: str) -> tuple[dict[str, str], str]:
    response = await client.post(
        "/auth/register",
        json={"email": f"{name}@types.test", "nickname": name, "password": "TestPass123", "email_code": "123456"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, response.json()["id"]


async def add_type(key: str, name: str, dimension: str, owner_user_id: str | None = None, enabled: bool = True) -> None:
    async with async_session() as db:
        db.add(
            InspectionType(
                key=key,
                name=name,
                dimension=dimension,
                owner_type="user" if owner_user_id else "system",
                owner_user_id=owner_user_id,
                enabled=enabled,
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_type_crud_isolated_and_system_types_are_protected(client: AsyncClient):
    user_a, user_a_id = await register(client, "type-a")
    user_b, user_b_id = await register(client, "type-b")
    await add_type("general-engineering", "通用工程", "engineering")
    await add_type("a-private", "甲方类别", "engineering", user_a_id)
    await add_type("b-private", "乙方类别", "engineering", user_b_id)

    response = await client.get("/inspection/engineering-types", headers=user_a)
    assert response.status_code == 200
    assert {item["key"] for item in response.json()} == {"general-engineering", "a-private"}

    system_id = next(item["id"] for item in response.json() if item["owner_type"] == "system")
    forbidden = await client.patch(
        f"/inspection/engineering-types/{system_id}", headers=user_a, json={"name": "不应修改"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "system_type_protected"

    created = await client.post(
        "/inspection/engineering-types", headers=user_a, json={"key": "new-private", "name": "新类别"}
    )
    assert created.status_code == 201
    updated = await client.patch(
        f"/inspection/engineering-types/{created.json()['id']}", headers=user_a, json={"name": "新名称"}
    )
    assert updated.status_code == 200
    cross_user = await client.patch(
        f"/inspection/engineering-types/{created.json()['id']}", headers=user_b, json={"name": "越权"}
    )
    assert cross_user.status_code == 404


@pytest.mark.asyncio
async def test_type_validation_duplicate_disable_and_referenced_delete(client: AsyncClient):
    headers, user_id = await register(client, "type-validation")
    await add_type("existing", "重复名称", "contract", user_id)

    invalid = await client.post(
        "/inspection/contract-types", headers=headers, json={"key": "", "name": "有效", "dimension": "engineering"}
    )
    assert invalid.status_code == 422
    duplicate = await client.post(
        "/inspection/contract-types", headers=headers, json={"key": "another", "name": "重复名称"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_inspection_type"

    created = await client.post(
        "/inspection/contract-types", headers=headers, json={"key": "referenced", "name": "被引用"}
    )
    type_id = created.json()["id"]
    async with async_session() as db:
        db.add(
            InspectionRecord(
                user_id=user_id,
                document_name="合同.txt",
                document_type="contract",
                document_type_label="合同",
                overall_risk="low",
                summary="summary",
                issues=[],
                regulation_refs=[],
                final_contract_type="referenced",
            )
        )
        await db.commit()

    delete_response = await client.delete(f"/inspection/contract-types/{type_id}", headers=headers)
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"]["code"] == "inspection_type_in_use"
    disabled = await client.patch(
        f"/inspection/contract-types/{type_id}", headers=headers, json={"enabled": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert len((await client.get("/inspection/contract-types", headers=headers)).json()) == 1


def test_openapi_exposes_eight_type_operations():
    paths = app.openapi()["paths"]
    expected = {
        (method, f"/inspection/{dimension}-types{suffix}")
        for dimension in ("engineering", "contract")
        for method, suffix in (("get", ""), ("post", ""), ("patch", "/{type_id}"), ("delete", "/{type_id}"))
    }
    actual = {(method, path) for path, item in paths.items() if "types" in path for method in item}
    assert expected <= actual
