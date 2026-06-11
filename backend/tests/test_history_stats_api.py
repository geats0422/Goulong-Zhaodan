from __future__ import annotations

import types
from datetime import date
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fake_inspector_module = types.ModuleType("agents.inspector")
fake_inspector_module.InspectionResult = dict


async def _fake_run_inspection(*args, **kwargs):  # noqa: ANN002, ANN003
    return {"overall_risk": "low", "summary": "", "issues": [], "regulation_refs": []}


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["agents.inspector"] = fake_inspector_module

from main import app  # noqa: E402
from core.auth import get_current_user  # noqa: E402


async def _override_user():
    return {"user_id": "1", "username": "testuser", "is_active": True}


API_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user] = _override_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_history_stats_aggregation_unit() -> None:
    from routers.inspection import _aggregate_history_stats

    today = date.today().isoformat()
    records = [
        {
            "id": 1,
            "user_id": 1,
            "project_id": "default",
            "document_name": "a.txt",
            "issues": [{"title": "违规"}],
            "created_at": today,
            "quota_consumed": 10,
        },
        {
            "id": 2,
            "user_id": 1,
            "project_id": "default",
            "document_name": "b.txt",
            "issues": [],
            "created_at": today,
            "quota_consumed": 5,
        },
    ]
    result = _aggregate_history_stats(records, days=7)
    assert result.summary.total_docs == 2
    assert result.summary.hit_docs == 1
    assert result.summary.banned_rate == 0.5
    assert result.summary.quota_consumed == 15
    assert sum(result.trend.total_docs) == result.summary.total_docs
    assert sum(result.trend.hit_docs) == result.summary.hit_docs
    assert sum(result.trend.quota_consumed) == result.summary.quota_consumed


def test_history_stats_empty_input() -> None:
    from routers.inspection import _aggregate_history_stats

    result = _aggregate_history_stats([], days=7)
    assert result.summary.total_docs == 0
    assert result.summary.hit_docs == 0
    assert result.summary.banned_rate == 0
    assert len(result.trend.dates) == 7


def test_missing_api_key_returns_401() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        clean_client = TestClient(app)
        response = clean_client.get("/inspection/stats/history")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = _override_user


def test_invalid_api_key_returns_401() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        clean_client = TestClient(app)
        response = clean_client.get(
            "/inspection/stats/history",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = _override_user
