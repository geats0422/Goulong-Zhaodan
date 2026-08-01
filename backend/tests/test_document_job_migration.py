from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, Column, ForeignKeyConstraint

from app.models.document_job import (
    DOCUMENT_JOB_STAGES,
    DOCUMENT_JOB_STATUSES,
    DOCUMENT_JOB_TYPES,
    DOCUMENT_PARSER_ENGINES,
)
from tests.test_document_job_model import EXPECTED_CHECKS, EXPECTED_COLUMNS


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "019_document_processing_jobs.py"
_POST_019_COLUMNS = {
    "lease_version",
    "dispatch_pending",
    "dispatch_retry_count",
    "next_dispatch_at",
    "dispatch_claim_owner",
    "dispatch_claim_expires_at",
    "lease_owner",
    "lease_expires_at",
    "mineru_task_id",
    "mineru_upload_state",
    "index_artifact_path",
    "index_artifact_hash",
    "inspection_call_state",
    "inspection_input_hash",
    "inspection_result_path",
    "inspection_result_hash",
}
EXPECTED_019_COLUMNS = {name: contract for name, contract in EXPECTED_COLUMNS.items() if name not in _POST_019_COLUMNS}
EXPECTED_019_CHECKS = {
    name: condition
    for name, condition in EXPECTED_CHECKS.items()
    if name
    not in {
        "ck_document_processing_jobs_lease_version_nonnegative",
        "ck_document_processing_jobs_markdown_pair",
        "ck_document_processing_jobs_succeeded_artifact",
        "ck_document_processing_jobs_dispatch_retry_nonnegative",
        "ck_document_processing_jobs_dispatch_claim_pair",
        "ck_document_processing_jobs_lease_pair",
        "ck_document_processing_jobs_index_artifact_pair",
        "ck_document_processing_jobs_index_artifact_hash",
        "ck_document_processing_jobs_inspection_call_state",
        "ck_document_processing_jobs_inspection_input_hash",
        "ck_document_processing_jobs_inspection_result_pair",
        "ck_document_processing_jobs_inspection_result_hash",
        "ck_document_processing_jobs_mineru_upload_state",
    }
}


@pytest.fixture(scope="session")
def _ensure_schema():
    """Migration unit tests do not require PostgreSQL."""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """No rows are created."""


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_019", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperationRecorder:
    def __init__(self) -> None:
        self.created_table: tuple[str, tuple[Any, ...], dict[str, Any]] | None = None
        self.created_indexes: list[tuple[str, str, tuple[str, ...], dict[str, Any]]] = []
        self.events: list[tuple[str, str]] = []

    def create_table(self, name: str, *items: Any, **kwargs: Any) -> None:
        self.created_table = (name, items, kwargs)

    def create_index(self, name: str, table_name: str, columns: list[str], **kwargs: Any) -> None:
        self.created_indexes.append((name, table_name, tuple(columns), kwargs))

    def drop_index(self, name: str, **kwargs: Any) -> None:
        assert kwargs == {"table_name": "document_processing_jobs", "schema": "zhaodan"}
        self.events.append(("drop_index", name))

    def drop_table(self, name: str, **kwargs: Any) -> None:
        assert kwargs == {"schema": "zhaodan"}
        self.events.append(("drop_table", name))


def test_migration_019_follows_revision_018_and_freezes_allowed_values() -> None:
    migration = _load_migration()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert migration.revision == "019"
    assert migration.down_revision == "018"
    assert "from app" not in source
    assert migration.DOCUMENT_JOB_TYPES == DOCUMENT_JOB_TYPES
    assert migration.DOCUMENT_JOB_STATUSES == DOCUMENT_JOB_STATUSES
    assert migration.DOCUMENT_JOB_STAGES == DOCUMENT_JOB_STAGES
    assert migration.DOCUMENT_PARSER_ENGINES == DOCUMENT_PARSER_ENGINES


def test_alembic_console_can_load_revision_graph() -> None:
    executable_name = "alembic.exe" if os.name == "nt" else "alembic"
    alembic_executable = Path(sys.executable).with_name(executable_name)

    result = subprocess.run(
        [str(alembic_executable), "heads"],
        cwd=MIGRATION_PATH.parents[2],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "030 (head)"


def test_upgrade_columns_match_model_types_nullability_defaults_and_timezone(monkeypatch) -> None:
    migration = _load_migration()
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)

    migration.upgrade()

    assert recorder.created_table is not None
    table_name, items, kwargs = recorder.created_table
    columns = {item.name: item for item in items if isinstance(item, Column)}
    assert table_name == "document_processing_jobs"
    assert kwargs == {"schema": "zhaodan"}
    assert set(columns) == set(EXPECTED_019_COLUMNS)

    for name, (type_class, length, nullable) in EXPECTED_019_COLUMNS.items():
        column = columns[name]
        assert isinstance(column.type, type_class), name
        assert getattr(column.type, "length", None) == length, name
        assert column.nullable is nullable, name

    assert columns["id"].type.as_uuid is True
    assert columns["user_id"].type.as_uuid is True
    for name in ("created_at", "updated_at", "finished_at"):
        assert columns[name].type.timezone is True
    assert {
        name: str(columns[name].server_default.arg)
        for name in ("status", "stage", "progress", "retry_count", "parser_version")
    } == {
        "status": "queued",
        "stage": "queued",
        "progress": "0",
        "retry_count": "0",
        "parser_version": "1",
    }
    assert str(columns["created_at"].server_default.arg) == "now()"
    assert str(columns["updated_at"].server_default.arg) == "now()"
    assert columns["finished_at"].server_default is None


def test_upgrade_foreign_keys_checks_and_indexes_match_model_contract(monkeypatch) -> None:
    migration = _load_migration()
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)

    migration.upgrade()

    assert recorder.created_table is not None
    _, items, _ = recorder.created_table
    foreign_keys = {
        tuple(item.column_keys): (tuple(element.target_fullname for element in item.elements), item.ondelete)
        for item in items
        if isinstance(item, ForeignKeyConstraint)
    }
    checks = {item.name: str(item.sqltext) for item in items if isinstance(item, CheckConstraint)}

    assert foreign_keys == {
        ("user_id",): (("goulong_auth.users.id",), "CASCADE"),
        ("knowledge_version_id",): (("zhaodan.document_versions.id",), "SET NULL"),
        ("inspection_record_id",): (("zhaodan.inspection_records.id",), "SET NULL"),
    }
    assert checks == EXPECTED_019_CHECKS
    assert recorder.created_indexes == [
        (
            "ix_document_processing_jobs_user_created_at",
            "document_processing_jobs",
            ("user_id", "created_at"),
            {"schema": "zhaodan"},
        ),
        (
            "ix_document_processing_jobs_status",
            "document_processing_jobs",
            ("status",),
            {"schema": "zhaodan"},
        ),
        (
            "ix_document_processing_jobs_user_hash_parser_version",
            "document_processing_jobs",
            ("user_id", "content_hash", "parser_version"),
            {"schema": "zhaodan"},
        ),
    ]


def test_downgrade_drops_indexes_before_table(monkeypatch) -> None:
    migration = _load_migration()
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)

    migration.downgrade()

    assert recorder.events == [
        ("drop_index", "ix_document_processing_jobs_user_hash_parser_version"),
        ("drop_index", "ix_document_processing_jobs_status"),
        ("drop_index", "ix_document_processing_jobs_user_created_at"),
        ("drop_table", "document_processing_jobs"),
    ]
