from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.models.knowledge import InspectionRecord
from app.services.contract_classifier import ContractClassification
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
