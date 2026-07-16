from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models import DocumentProcessingJob
from app.models.document_job import (
    DOCUMENT_JOB_STAGES,
    DOCUMENT_JOB_STATUSES,
    DOCUMENT_JOB_TYPES,
    DOCUMENT_PARSER_ENGINES,
)


EXPECTED_COLUMNS = {
    "id": (UUID, None, False),
    "job_id": (String, 100, False),
    "user_id": (UUID, None, False),
    "job_type": (String, 50, False),
    "source_path": (String, 1000, False),
    "content_hash": (String, 64, False),
    "file_type": (String, 20, False),
    "status": (String, 20, False),
    "stage": (String, 30, False),
    "progress": (Integer, None, False),
    "message": (Text, None, True),
    "parser_engine": (String, 50, True),
    "mineru_task_id": (String, 200, True),
    "mineru_upload_state": (String, 20, True),
    "markdown_path": (String, 1000, True),
    "markdown_hash": (String, 64, True),
    "index_artifact_path": (String, 1000, True),
    "index_artifact_hash": (String, 64, True),
    "inspection_call_state": (String, 20, True),
    "inspection_input_hash": (String, 64, True),
    "inspection_result_path": (String, 1000, True),
    "inspection_result_hash": (String, 64, True),
    "knowledge_version_id": (Integer, None, True),
    "inspection_record_id": (Integer, None, True),
    "error_code": (String, 50, True),
    "error_message": (Text, None, True),
    "retry_count": (Integer, None, False),
    "dispatch_pending": (Boolean, None, False),
    "dispatch_retry_count": (Integer, None, False),
    "next_dispatch_at": (DateTime, None, False),
    "dispatch_claim_owner": (String, 100, True),
    "dispatch_claim_expires_at": (DateTime, None, True),
    "lease_version": (Integer, None, False),
    "lease_owner": (String, 100, True),
    "lease_expires_at": (DateTime, None, True),
    "parser_version": (String, 50, False),
    "created_at": (DateTime, None, False),
    "updated_at": (DateTime, None, False),
    "finished_at": (DateTime, None, True),
}

EXPECTED_CHECKS = {
    "ck_document_processing_jobs_status": "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
    "ck_document_processing_jobs_stage": (
        "stage IN ('queued', 'detecting', 'parsing_local', 'parsing_mineru', 'indexing', 'inspecting', 'succeeded', "
        "'failed')"
    ),
    "ck_document_processing_jobs_job_type": "job_type IN ('inspection', 'knowledge', 'agent_parse')",
    "ck_document_processing_jobs_parser_engine": (
        "parser_engine IS NULL OR parser_engine IN ('text', 'markitdown', 'mineru')"
    ),
    "ck_document_processing_jobs_content_hash": "content_hash ~ '^[0-9a-f]{64}$'",
    "ck_document_processing_jobs_markdown_hash": ("markdown_hash IS NULL OR markdown_hash ~ '^[0-9a-f]{64}$'"),
    "ck_document_processing_jobs_index_artifact_hash": (
        "index_artifact_hash IS NULL OR index_artifact_hash ~ '^[0-9a-f]{64}$'"
    ),
    "ck_document_processing_jobs_inspection_input_hash": (
        "inspection_input_hash IS NULL OR inspection_input_hash ~ '^[0-9a-f]{64}$'"
    ),
    "ck_document_processing_jobs_inspection_result_hash": (
        "inspection_result_hash IS NULL OR inspection_result_hash ~ '^[0-9a-f]{64}$'"
    ),
    "ck_document_processing_jobs_progress_range": "progress BETWEEN 0 AND 100",
    "ck_document_processing_jobs_retry_count_nonnegative": "retry_count >= 0",
    "ck_document_processing_jobs_lease_version_nonnegative": "lease_version >= 0",
    "ck_document_processing_jobs_dispatch_retry_nonnegative": "dispatch_retry_count >= 0",
    "ck_document_processing_jobs_dispatch_claim_pair": (
        "(dispatch_claim_owner IS NULL) = (dispatch_claim_expires_at IS NULL)"
    ),
    "ck_document_processing_jobs_lease_pair": "(lease_owner IS NULL) = (lease_expires_at IS NULL)",
    "ck_document_processing_jobs_markdown_pair": (
        "(markdown_path IS NULL AND markdown_hash IS NULL) OR (markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)"
    ),
    "ck_document_processing_jobs_index_artifact_pair": (
        "(index_artifact_path IS NULL) = (index_artifact_hash IS NULL)"
    ),
    "ck_document_processing_jobs_inspection_result_pair": (
        "(inspection_result_path IS NULL) = (inspection_result_hash IS NULL)"
    ),
    "ck_document_processing_jobs_inspection_call_state": (
        "inspection_call_state IS NULL OR inspection_call_state IN ('started', 'completed')"
    ),
    "ck_document_processing_jobs_mineru_upload_state": (
        "(mineru_task_id IS NULL AND mineru_upload_state IS NULL) OR "
        "(mineru_task_id IS NOT NULL AND mineru_upload_state IN ('pending', 'uploaded'))"
    ),
    "ck_document_processing_jobs_succeeded_artifact": (
        "status <> 'succeeded' OR "
        "(parser_engine IS NOT NULL AND markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)"
    ),
    "ck_document_processing_jobs_state_consistency": (
        "(status = 'queued' AND stage = 'queued' AND progress = 0 AND finished_at IS NULL AND error_code IS NULL) OR "
        "(status = 'running' AND stage IN ('detecting', 'parsing_local', 'parsing_mineru', 'indexing', 'inspecting') "
        "AND progress BETWEEN 0 AND 99 AND finished_at IS NULL AND error_code IS NULL) OR "
        "(status = 'succeeded' AND stage = 'succeeded' AND progress = 100 AND finished_at IS NOT NULL AND "
        "error_code IS NULL) OR "
        "(status = 'failed' AND stage = 'failed' AND finished_at IS NOT NULL AND error_code IS NOT NULL) OR "
        "(status = 'cancelled' AND stage NOT IN ('succeeded', 'failed') AND progress BETWEEN 0 AND 99 AND "
        "finished_at IS NOT NULL AND error_code IS NULL)"
    ),
}


@pytest.fixture(scope="session")
def _ensure_schema():
    """Model metadata tests do not require PostgreSQL."""


@pytest.fixture(autouse=True)
def _cleanup_before_test():
    """No rows are created."""


def test_document_job_allowed_values_are_centralized() -> None:
    assert DOCUMENT_JOB_TYPES == ("inspection", "knowledge", "agent_parse")
    assert DOCUMENT_JOB_STATUSES == ("queued", "running", "succeeded", "failed", "cancelled")
    assert DOCUMENT_JOB_STAGES == (
        "queued",
        "detecting",
        "parsing_local",
        "parsing_mineru",
        "indexing",
        "inspecting",
        "succeeded",
        "failed",
    )
    assert DOCUMENT_PARSER_ENGINES == ("text", "markitdown", "mineru")


def test_document_processing_job_columns_have_exact_schema_types_and_nullability() -> None:
    table = DocumentProcessingJob.__table__

    assert table.schema == "zhaodan"
    assert set(table.c.keys()) == set(EXPECTED_COLUMNS)
    for name, (type_class, length, nullable) in EXPECTED_COLUMNS.items():
        column = table.c[name]
        assert isinstance(column.type, type_class), name
        assert getattr(column.type, "length", None) == length, name
        assert column.nullable is nullable, name

    assert table.c.id.primary_key
    assert table.c.id.type.as_uuid is True
    assert table.c.user_id.type.as_uuid is True
    assert table.c.job_id.unique
    for name in (
        "created_at",
        "updated_at",
        "finished_at",
        "next_dispatch_at",
        "dispatch_claim_expires_at",
        "lease_expires_at",
    ):
        assert table.c[name].type.timezone is True


def test_document_processing_job_defaults_support_a_new_queued_job() -> None:
    user_id = uuid.uuid4()
    job = DocumentProcessingJob(
        job_id="doc_job_001",
        user_id=user_id,
        job_type="knowledge",
        source_path="uploads/user/document.pdf",
        content_hash="a" * 64,
        file_type="pdf",
    )
    columns = DocumentProcessingJob.__table__.c

    assert job.user_id == user_id
    assert columns.status.default.arg == "queued"
    assert str(columns.status.server_default.arg) == "queued"
    assert columns.stage.default.arg == "queued"
    assert str(columns.stage.server_default.arg) == "queued"
    assert columns.progress.default.arg == 0
    assert str(columns.progress.server_default.arg) == "0"
    assert columns.retry_count.default.arg == 0
    assert str(columns.retry_count.server_default.arg) == "0"
    assert columns.dispatch_pending.default.arg is True
    assert str(columns.dispatch_pending.server_default.arg) == "true"
    assert columns.dispatch_retry_count.default.arg == 0
    assert str(columns.dispatch_retry_count.server_default.arg) == "0"
    assert columns.lease_version.default.arg == 0
    assert str(columns.lease_version.server_default.arg) == "0"
    assert columns.parser_version.default.arg == "1"
    assert str(columns.parser_version.server_default.arg) == "1"
    assert str(columns.created_at.server_default.arg) == "now()"
    assert str(columns.updated_at.server_default.arg) == "now()"
    assert columns.finished_at.server_default is None
    assert columns.markdown_hash.server_default is None


def test_document_processing_job_foreign_keys_define_safe_delete_actions() -> None:
    table = DocumentProcessingJob.__table__
    foreign_keys = {
        column.name: (foreign_key.target_fullname, foreign_key.ondelete)
        for column in table.columns
        for foreign_key in column.foreign_keys
    }

    assert foreign_keys == {
        "user_id": ("goulong_auth.users.id", "CASCADE"),
        "knowledge_version_id": ("zhaodan.document_versions.id", "SET NULL"),
        "inspection_record_id": ("zhaodan.inspection_records.id", "SET NULL"),
    }


def test_document_processing_job_check_constraints_match_allowed_values() -> None:
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in DocumentProcessingJob.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert checks == EXPECTED_CHECKS


def test_document_processing_job_indexes_support_queries_and_hash_reuse() -> None:
    indexes = {
        index.name: tuple(column.name for column in index.columns) for index in DocumentProcessingJob.__table__.indexes
    }

    assert indexes == {
        "ix_document_processing_jobs_user_created_at": ("user_id", "created_at"),
        "ix_document_processing_jobs_status": ("status",),
        "ix_document_processing_jobs_user_hash_parser_version": (
            "user_id",
            "content_hash",
            "parser_version",
        ),
        "ix_document_processing_jobs_markdown_cache": (
            "user_id",
            "content_hash",
            "parser_version",
            "status",
            "finished_at",
        ),
        "ix_document_processing_jobs_dispatch_pending": ("dispatch_pending", "next_dispatch_at"),
        "ix_document_processing_jobs_expired_lease": ("status", "lease_expires_at"),
    }
    cache_index = next(
        index
        for index in DocumentProcessingJob.__table__.indexes
        if index.name == "ix_document_processing_jobs_markdown_cache"
    )
    assert str(cache_index.dialect_options["postgresql"]["where"]) == "status = 'succeeded'"
