"""add recoverable remote and stage artifacts

Revision ID: 022
Revises: 021
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "022"
down_revision: str | None = "021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"
TABLE = "document_processing_jobs"


def upgrade() -> None:
    for column in (
        sa.Column("mineru_task_id", sa.String(length=200), nullable=True),
        sa.Column("mineru_upload_state", sa.String(length=20), nullable=True),
        sa.Column("index_artifact_path", sa.String(length=1000), nullable=True),
        sa.Column("index_artifact_hash", sa.String(length=64), nullable=True),
        sa.Column("inspection_call_state", sa.String(length=20), nullable=True),
        sa.Column("inspection_input_hash", sa.String(length=64), nullable=True),
        sa.Column("inspection_result_path", sa.String(length=1000), nullable=True),
        sa.Column("inspection_result_hash", sa.String(length=64), nullable=True),
    ):
        op.add_column(TABLE, column, schema=SCHEMA)
    op.create_check_constraint(
        "ck_document_processing_jobs_mineru_upload_state",
        TABLE,
        "(mineru_task_id IS NULL AND mineru_upload_state IS NULL) OR "
        "(mineru_task_id IS NOT NULL AND mineru_upload_state IN ('pending', 'uploaded'))",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_index_artifact_pair",
        TABLE,
        "(index_artifact_path IS NULL) = (index_artifact_hash IS NULL)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_inspection_result_pair",
        TABLE,
        "(inspection_result_path IS NULL) = (inspection_result_hash IS NULL)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_inspection_call_state",
        TABLE,
        "inspection_call_state IS NULL OR inspection_call_state IN ('started', 'completed')",
        schema=SCHEMA,
    )
    for name, expression in (
        (
            "ck_document_processing_jobs_index_artifact_hash",
            "index_artifact_hash IS NULL OR index_artifact_hash ~ '^[0-9a-f]{64}$'",
        ),
        (
            "ck_document_processing_jobs_inspection_input_hash",
            "inspection_input_hash IS NULL OR inspection_input_hash ~ '^[0-9a-f]{64}$'",
        ),
        (
            "ck_document_processing_jobs_inspection_result_hash",
            "inspection_result_hash IS NULL OR inspection_result_hash ~ '^[0-9a-f]{64}$'",
        ),
    ):
        op.create_check_constraint(name, TABLE, expression, schema=SCHEMA)


def downgrade() -> None:
    for name in (
        "ck_document_processing_jobs_inspection_result_hash",
        "ck_document_processing_jobs_inspection_input_hash",
        "ck_document_processing_jobs_index_artifact_hash",
        "ck_document_processing_jobs_inspection_call_state",
        "ck_document_processing_jobs_inspection_result_pair",
        "ck_document_processing_jobs_index_artifact_pair",
        "ck_document_processing_jobs_mineru_upload_state",
    ):
        op.drop_constraint(name, TABLE, type_="check", schema=SCHEMA)
    for column in (
        "inspection_result_hash",
        "inspection_result_path",
        "inspection_input_hash",
        "inspection_call_state",
        "index_artifact_hash",
        "index_artifact_path",
        "mineru_upload_state",
        "mineru_task_id",
    ):
        op.drop_column(TABLE, column, schema=SCHEMA)
