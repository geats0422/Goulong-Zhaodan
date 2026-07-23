"""add inspection record status

Revision ID: 024
Revises: 023
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: str | None = "023"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"
TABLE = "inspection_records"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
        schema=SCHEMA,
    )
    op.execute(
        "UPDATE zhaodan.inspection_records SET status = CASE "
        "WHEN overall_risk = 'pending' OR (json_array_length(issues) = 0 AND COALESCE(parsed_content, '') = '') THEN 'processing' "
        "ELSE 'completed' END"
    )
    op.execute(
        "UPDATE zhaodan.inspection_records AS record SET status = 'failed' "
        "WHERE EXISTS (SELECT 1 FROM zhaodan.document_processing_jobs AS job "
        "WHERE job.inspection_record_id = record.id AND job.status = 'failed')"
    )
    op.create_check_constraint(
        "ck_inspection_records_status",
        TABLE,
        "status IN ('uploaded', 'processing', 'completed', 'failed', 'cancelled')",
        schema=SCHEMA,
    )
    op.create_index("ix_inspection_records_user_created_at", TABLE, ["user_id", "created_at"], schema=SCHEMA)
    op.create_index("ix_inspection_records_user_project_created_at", TABLE, ["user_id", "project_id", "created_at"], schema=SCHEMA)
    op.create_index("ix_inspection_records_user_status_created_at", TABLE, ["user_id", "status", "created_at"], schema=SCHEMA)
    op.alter_column(TABLE, "status", server_default=None, schema=SCHEMA)


def downgrade() -> None:
    for index in (
        "ix_inspection_records_user_status_created_at",
        "ix_inspection_records_user_project_created_at",
        "ix_inspection_records_user_created_at",
    ):
        op.drop_index(index, table_name=TABLE, schema=SCHEMA)
    op.drop_constraint("ck_inspection_records_status", TABLE, schema=SCHEMA)
    op.drop_column(TABLE, "status", schema=SCHEMA)
