from __future__ import annotations

import uuid
from datetime import date, datetime

from app.api.v1.inspection import _aggregate_history_stats  # noqa: E402
from app.models.knowledge import InspectionRecord  # noqa: E402


def test_history_stats_empty_data() -> None:
    stats = _aggregate_history_stats([])

    assert stats.range == "7d"
    assert stats.summary.uploaded_docs == 0
    assert stats.summary.completed_docs == 0
    assert stats.summary.hit_docs == 0
    assert stats.summary.hit_rate == 0
    assert stats.summary.quota_consumed == 0
    assert len(stats.trend.dates) == 7
    assert len(stats.trend.uploaded_docs) == 7


def test_history_stats_aggregation_and_rate() -> None:
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    today = datetime.combine(date.today(), datetime.min.time())
    records = [
        InspectionRecord(user_id=user_id, document_name="a.txt", document_type="bidding", document_type_label="招投标", overall_risk="high", summary="", issues=[{"title": "违规"}], regulation_refs=[], status="completed", quota_consumed=10, created_at=today),
        InspectionRecord(user_id=user_id, document_name="b.txt", document_type="bidding", document_type_label="招投标", overall_risk="low", summary="", issues=[], regulation_refs=[], status="completed", quota_consumed=5, created_at=today),
        InspectionRecord(user_id=user_id, document_name="c.txt", document_type="bidding", document_type_label="招投标", overall_risk="pending", summary="", issues=[], regulation_refs=[], status="processing", quota_consumed=0, created_at=today),
        InspectionRecord(user_id=user_id, document_name="d.txt", document_type="bidding", document_type_label="招投标", overall_risk="failed", summary="", issues=[], regulation_refs=[], status="failed", quota_consumed=0, created_at=today),
    ]
    stats = _aggregate_history_stats(records)

    assert stats.summary.uploaded_docs == 4
    assert stats.summary.completed_docs == 2
    assert stats.summary.hit_docs == 1
    assert stats.summary.failed_docs == 1
    assert stats.summary.pending_docs == 1
    assert stats.summary.hit_rate == 0.5
    assert stats.summary.quota_consumed == 15
    assert sum(stats.trend.uploaded_docs) == stats.summary.uploaded_docs
    assert sum(stats.trend.hit_docs) == stats.summary.hit_docs
    assert sum(stats.trend.quota_consumed) == stats.summary.quota_consumed
