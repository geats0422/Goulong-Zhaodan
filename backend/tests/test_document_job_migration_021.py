from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "021_document_job_dispatch_lease.py"


@pytest.fixture(scope="session")
def _ensure_schema():
    """Migration shape test does not require PostgreSQL."""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """No rows are created."""


def test_021_is_next_revision_and_adds_dispatch_and_lease_columns() -> None:
    spec = importlib.util.spec_from_file_location("migration_021", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "021"
    assert migration.down_revision == "020"
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    for column in (
        "dispatch_pending",
        "dispatch_retry_count",
        "next_dispatch_at",
        "dispatch_claim_owner",
        "dispatch_claim_expires_at",
        "lease_owner",
        "lease_expires_at",
    ):
        assert column in source
    assert "ix_document_processing_jobs_dispatch_pending" in source
