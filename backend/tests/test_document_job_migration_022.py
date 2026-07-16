from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "022_document_job_resume_artifacts.py"


@pytest.fixture(scope="session")
def _ensure_schema():
    pass


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    pass


def test_022_adds_recoverable_remote_and_stage_artifacts() -> None:
    assert MIGRATION_PATH.exists()
    spec = importlib.util.spec_from_file_location("migration_022", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "022"
    assert migration.down_revision == "021"
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    for column in (
        "mineru_task_id",
        "mineru_upload_state",
        "index_artifact_path",
        "index_artifact_hash",
        "inspection_call_state",
        "inspection_input_hash",
        "inspection_result_path",
        "inspection_result_hash",
    ):
        assert column in source
    for constraint in (
        "ck_document_processing_jobs_mineru_upload_state",
        "ck_document_processing_jobs_index_artifact_hash",
        "ck_document_processing_jobs_inspection_input_hash",
        "ck_document_processing_jobs_inspection_result_hash",
    ):
        assert constraint in source


def test_022_upgrade_creates_each_check_with_valid_alembic_signature() -> None:
    spec = importlib.util.spec_from_file_location("migration_022_upgrade", MIGRATION_PATH)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = Mock()

    migration.upgrade()

    calls = migration.op.create_check_constraint.call_args_list
    assert all(len(call.args) == 3 for call in calls)
    assert {call.args[0] for call in calls} >= {
        "ck_document_processing_jobs_mineru_upload_state",
        "ck_document_processing_jobs_index_artifact_pair",
    }
