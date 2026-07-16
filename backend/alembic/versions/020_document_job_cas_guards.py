"""add document job CAS guards and artifact constraints

Revision ID: 020
Revises: 019
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "020"
down_revision: str | None = "019"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"
TABLE = "document_processing_jobs"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("lease_version", sa.Integer(), server_default="0", nullable=False),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_lease_version_nonnegative",
        TABLE,
        "lease_version >= 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_markdown_pair",
        TABLE,
        "(markdown_path IS NULL AND markdown_hash IS NULL) OR "
        "(markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_succeeded_artifact",
        TABLE,
        "status <> 'succeeded' OR "
        "(parser_engine IS NOT NULL AND markdown_path IS NOT NULL AND markdown_hash IS NOT NULL)",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_document_processing_jobs_markdown_cache",
        TABLE,
        ["user_id", "content_hash", "parser_version", "status", "finished_at"],
        unique=False,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'succeeded'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_processing_jobs_markdown_cache",
        table_name=TABLE,
        schema=SCHEMA,
    )
    for name in (
        "ck_document_processing_jobs_succeeded_artifact",
        "ck_document_processing_jobs_markdown_pair",
        "ck_document_processing_jobs_lease_version_nonnegative",
    ):
        op.drop_constraint(name, TABLE, type_="check", schema=SCHEMA)
    op.drop_column(TABLE, "lease_version", schema=SCHEMA)
