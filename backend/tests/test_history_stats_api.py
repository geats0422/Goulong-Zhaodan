from __future__ import annotations

import types
from datetime import date
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fake_inspector_module = types.ModuleType("agents.inspector")
fake_inspector_module.InspectionResult = dict


async def _fake_run_inspection(*args, **kwargs):  # noqa: ANN002, ANN003
    return {"overall_risk": "low", "summary": "", "issues": [], "regulation_refs": []}


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["agents.inspector"] = fake_inspector_module

from main import app  # noqa: E402
from routers import inspection as inspection_router  # noqa: E402


client = TestClient(app)

API_HEADERS = {"X-API-Key": "goulong-dev-key"}


def setup_function() -> None:
    inspection_router._inspection_records.clear()


def test_history_stats_empty_data() -> None:
    response = client.get("/inspection/stats/history", headers=API_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["range"] == "7d"
    assert data["summary"]["total_docs"] == 0
    assert data["summary"]["hit_docs"] == 0
    assert data["summary"]["banned_rate"] == 0
    assert data["summary"]["quota_consumed"] == 0
    assert len(data["trend"]["dates"]) == 7
    assert len(data["trend"]["total_docs"]) == 7


def test_history_stats_aggregation_and_rate() -> None:
    today = date.today().isoformat()
    inspection_router._inspection_records.extend(
        [
            {
                "id": 1,
                "project_id": "default",
                "document_name": "a.txt",
                "issues": [{"title": "违规"}],
                "created_at": today,
                "quota_consumed": 10,
            },
            {
                "id": 2,
                "project_id": "default",
                "document_name": "b.txt",
                "issues": [],
                "created_at": today,
                "quota_consumed": 5,
            },
        ]
    )

    response = client.get("/inspection/stats/history", headers=API_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_docs"] == 2
    assert data["summary"]["hit_docs"] == 1
    assert data["summary"]["banned_rate"] == 0.5
    assert data["summary"]["quota_consumed"] == 15
    assert sum(data["trend"]["total_docs"]) == data["summary"]["total_docs"]
    assert sum(data["trend"]["hit_docs"]) == data["summary"]["hit_docs"]
    assert sum(data["trend"]["quota_consumed"]) == data["summary"]["quota_consumed"]


def test_missing_api_key_returns_401() -> None:
    response = client.get("/inspection/stats/history")
    assert response.status_code == 401
    assert "Missing API key" in response.json()["detail"]


def test_invalid_api_key_returns_401() -> None:
    response = client.get(
        "/inspection/stats/history",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]


def test_valid_api_key_returns_200() -> None:
    response = client.get("/inspection/stats/history", headers=API_HEADERS)
    assert response.status_code == 200
