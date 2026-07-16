from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import Column


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "020_document_job_cas_guards.py"


@pytest.fixture(scope="session")
def _ensure_schema():
    """Migration unit tests do not require PostgreSQL."""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """No rows are created."""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_020", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []

    def add_column(self, table: str, column: Column, **kwargs: Any) -> None:
        self.events.append(("add_column", table, column, kwargs))

    def create_check_constraint(self, name: str, table: str, condition: str, **kwargs: Any) -> None:
        self.events.append(("check", name, table, condition, kwargs))

    def create_index(self, name: str, table: str, columns: list[str], **kwargs: Any) -> None:
        self.events.append(("index", name, table, tuple(columns), kwargs))

    def drop_index(self, name: str, **kwargs: Any) -> None:
        self.events.append(("drop_index", name, kwargs))

    def drop_constraint(self, name: str, table: str, **kwargs: Any) -> None:
        self.events.append(("drop_constraint", name, table, kwargs))

    def drop_column(self, table: str, column: str, **kwargs: Any) -> None:
        self.events.append(("drop_column", table, column, kwargs))


def test_migration_020_adds_lease_constraints_and_partial_cache_index(monkeypatch) -> None:
    migration = _load()
    recorder = Recorder()
    monkeypatch.setattr(migration, "op", recorder)

    migration.upgrade()

    assert migration.revision == "020"
    assert migration.down_revision == "019"
    assert recorder.events[0][0:2] == ("add_column", "document_processing_jobs")
    column = recorder.events[0][2]
    assert column.name == "lease_version"
    assert column.nullable is False
    assert str(column.server_default.arg) == "0"
    checks = {event[1]: event[3] for event in recorder.events if event[0] == "check"}
    assert checks == {
        "ck_document_processing_jobs_lease_version_nonnegative": "lease_version >= 0",
        "ck_document_processing_jobs_markdown_pair": (
            "(markdown_path IS NULL AND markdown_hash IS NULL) OR "
            "(markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)"
        ),
        "ck_document_processing_jobs_succeeded_artifact": (
            "status <> 'succeeded' OR "
            "(parser_engine IS NOT NULL AND markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)"
        ),
    }
    index = next(event for event in recorder.events if event[0] == "index")
    assert index[1:4] == (
        "ix_document_processing_jobs_markdown_cache",
        "document_processing_jobs",
        ("user_id", "content_hash", "parser_version", "status", "finished_at"),
    )
    assert str(index[4]["postgresql_where"]) == "status = 'succeeded'"


def test_migration_020_downgrade_reverses_only_020_changes(monkeypatch) -> None:
    migration = _load()
    recorder = Recorder()
    monkeypatch.setattr(migration, "op", recorder)

    migration.downgrade()

    assert recorder.events == [
        (
            "drop_index",
            "ix_document_processing_jobs_markdown_cache",
            {"table_name": "document_processing_jobs", "schema": "zhaodan"},
        ),
        (
            "drop_constraint",
            "ck_document_processing_jobs_succeeded_artifact",
            "document_processing_jobs",
            {"type_": "check", "schema": "zhaodan"},
        ),
        (
            "drop_constraint",
            "ck_document_processing_jobs_markdown_pair",
            "document_processing_jobs",
            {"type_": "check", "schema": "zhaodan"},
        ),
        (
            "drop_constraint",
            "ck_document_processing_jobs_lease_version_nonnegative",
            "document_processing_jobs",
            {"type_": "check", "schema": "zhaodan"},
        ),
        ("drop_column", "document_processing_jobs", "lease_version", {"schema": "zhaodan"}),
    ]
