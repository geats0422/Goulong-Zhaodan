from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.knowledge import InspectionRecord
from app.models.compute import ComputeUsageRecord
from app.services.contract_classifier import ContractClassification
from app.services.compute_recorder import usage_idempotency_key
from app.services.compute_recorder import record_usage
from app.workers.tasks import _require_contract_scenario
from app.workers.tasks import _classification_record_values, _serialize_inspection_result


def test_classification_evidence_is_a_persisted_record_field() -> None:
    assert hasattr(InspectionRecord, "classification_evidence")
    classification = ContractClassification(
        engineering_type_key="municipal-road",
        contract_type_key="labor-subcontract",
        confidence="high",
        evidence=["正文命中市政道路", "正文命中劳务分包"],
        source="model",
        requires_confirmation=False,
    )

    values = _classification_record_values(classification, {"sources": []})

    assert values["classification_evidence"] == classification.evidence


def test_recovered_result_artifact_keeps_real_evidence() -> None:
    report = SimpleNamespace(issues=[], overall_risk="low", regulation_refs=[], summary="ok")
    classification = ContractClassification(
        engineering_type_key="municipal-road",
        contract_type_key="labor-subcontract",
        confidence="high",
        evidence=["市政道路"],
        source="model",
        requires_confirmation=False,
    )

    payload = json.loads(_serialize_inspection_result(report, classification=classification))

    assert payload["classification"]["evidence"] == ["市政道路"]


def test_classification_evidence_has_a_forward_migration_and_reversible_downgrade() -> None:
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "026_classification_evidence.py"
    source = migration.read_text(encoding="utf-8")

    assert 'revision: str = "026"' in source
    assert 'down_revision: str | None = "025"' in source
    assert '"classification_evidence"' in source
    assert "def downgrade()" in source


def test_usage_has_retry_idempotency_key_and_contract_scenario_guard() -> None:
    assert hasattr(ComputeUsageRecord, "idempotency_key")
    assert any(
        constraint.name == "uq_compute_usage_user_idempotency"
        for constraint in ComputeUsageRecord.__table__.constraints
    )
    assert usage_idempotency_key("job-1", "input-hash", "inspection_summary") == (
        "job-1:input-hash:inspection_summary"
    )

    try:
        _require_contract_scenario({"application_scenario": "bidding"})
    except ValueError as exc:
        assert str(exc) == "deprecated_application_scenario"
    else:
        raise AssertionError("bidding must be rejected before worker execution")


@pytest.mark.asyncio
async def test_completed_usage_is_reused_without_second_charge() -> None:
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            SimpleNamespace(scalar_one_or_none=lambda: None),
            SimpleNamespace(scalar_one_or_none=lambda: 37),
        ]
    )

    result = await record_usage(
        db,
        "12345678-1234-1234-1234-123456789012",
        business_type="inspection_summary",
        document_name="合同.txt",
        tokens_used=100,
        model_name="deepseek-chat",
        idempotency_key="job-1:input-hash:inspection_summary",
    )

    assert result == 37
    db.add.assert_not_called()


def test_usage_migration_uses_user_scoped_unique_key() -> None:
    from pathlib import Path

    source = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "027_compute_usage_idempotency.py"
    ).read_text(encoding="utf-8")
    assert '"idempotency_key"],\n        unique=True' in source
    assert '"ix_compute_usage_records_idempotency_key"' in source
    old_source = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "027_compute_usage_idempotency.py"
    ).read_text(encoding="utf-8")
    assert source == old_source

    migration_028 = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "028_compute_usage_user_unique.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "027"' in migration_028
    assert '"user_id", "idempotency_key"' in migration_028


def test_parse_response_is_processing_and_contract_placeholder() -> None:
    from app.api.v1.inspection import InspectionParseResponse

    assert "status" in InspectionParseResponse.model_fields


def test_archived_legacy_records_are_read_only() -> None:
    from app.services.inspection_history import is_archived_legacy_record

    assert is_archived_legacy_record({"document_type": "bidding"}) is True
    assert is_archived_legacy_record({"classification_source": "archived_legacy"}) is True
    assert is_archived_legacy_record({"document_type": "contract"}) is False
