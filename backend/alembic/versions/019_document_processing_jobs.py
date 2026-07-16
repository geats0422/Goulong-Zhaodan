"""add persistent document processing jobs

Revision ID: 019
Revises: 018
Create Date: 2026-07-16
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "019"
down_revision: str | None = "018"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"
TABLE_NAME = "document_processing_jobs"
DOCUMENT_JOB_TYPES = ("inspection", "knowledge", "agent_parse")
DOCUMENT_JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
DOCUMENT_JOB_STAGES = (
    "queued",
    "detecting",
    "parsing_local",
    "parsing_mineru",
    "indexing",
    "inspecting",
    "succeeded",
    "failed",
)
DOCUMENT_PARSER_ENGINES = ("text", "markitdown", "mineru")

_STATE_CONSISTENCY_SQL = (
    "(status = 'queued' AND stage = 'queued' AND progress = 0 AND finished_at IS NULL AND error_code IS NULL) OR "
    "(status = 'running' AND stage IN ('detecting', 'parsing_local', 'parsing_mineru', 'indexing', 'inspecting') "
    "AND progress BETWEEN 0 AND 99 AND finished_at IS NULL AND error_code IS NULL) OR "
    "(status = 'succeeded' AND stage = 'succeeded' AND progress = 100 AND finished_at IS NOT NULL AND "
    "error_code IS NULL) OR "
    "(status = 'failed' AND stage = 'failed' AND finished_at IS NOT NULL AND error_code IS NOT NULL) OR "
    "(status = 'cancelled' AND stage NOT IN ('succeeded', 'failed') AND progress BETWEEN 0 AND 99 AND "
    "finished_at IS NOT NULL AND error_code IS NULL)"
)


def _in_constraint(column: str, values: tuple[str, ...]) -> str:
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("source_path", sa.String(length=1000), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("stage", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("parser_engine", sa.String(length=50), nullable=True),
        sa.Column("markdown_path", sa.String(length=1000), nullable=True),
        sa.Column("markdown_hash", sa.String(length=64), nullable=True),
        sa.Column("knowledge_version_id", sa.Integer(), nullable=True),
        sa.Column("inspection_record_id", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("parser_version", sa.String(length=50), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_constraint("status", DOCUMENT_JOB_STATUSES),
            name="ck_document_processing_jobs_status",
        ),
        sa.CheckConstraint(
            _in_constraint("stage", DOCUMENT_JOB_STAGES),
            name="ck_document_processing_jobs_stage",
        ),
        sa.CheckConstraint(
            _in_constraint("job_type", DOCUMENT_JOB_TYPES),
            name="ck_document_processing_jobs_job_type",
        ),
        sa.CheckConstraint(
            f"parser_engine IS NULL OR {_in_constraint('parser_engine', DOCUMENT_PARSER_ENGINES)}",
            name="ck_document_processing_jobs_parser_engine",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_content_hash",
        ),
        sa.CheckConstraint(
            "markdown_hash IS NULL OR markdown_hash ~ '^[0-9a-f]{64}$'",
            name="ck_document_processing_jobs_markdown_hash",
        ),
        sa.CheckConstraint(
            "progress BETWEEN 0 AND 100",
            name="ck_document_processing_jobs_progress_range",
        ),
        sa.CheckConstraint(
            "retry_count >= 0",
            name="ck_document_processing_jobs_retry_count_nonnegative",
        ),
        sa.CheckConstraint(
            _STATE_CONSISTENCY_SQL,
            name="ck_document_processing_jobs_state_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["goulong_auth.users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_version_id"],
            [f"{SCHEMA}.document_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_record_id"],
            [f"{SCHEMA}.inspection_records.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_document_processing_jobs_job_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_document_processing_jobs_user_created_at",
        TABLE_NAME,
        ["user_id", "created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_document_processing_jobs_status",
        TABLE_NAME,
        ["status"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_document_processing_jobs_user_hash_parser_version",
        TABLE_NAME,
        ["user_id", "content_hash", "parser_version"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_processing_jobs_user_hash_parser_version",
        table_name=TABLE_NAME,
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_document_processing_jobs_status",
        table_name=TABLE_NAME,
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_document_processing_jobs_user_created_at",
        table_name=TABLE_NAME,
        schema=SCHEMA,
    )
    op.drop_table(TABLE_NAME, schema=SCHEMA)
