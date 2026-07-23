"""add compute usage records table

Revision ID: 023
Revises: 022
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "023"
down_revision: str | None = "022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"
TABLE_NAME = "compute_usage_records"


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("business_type", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Integer(), nullable=False),
        sa.Column("quota_consumed", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["goulong_auth.users.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index("ix_compute_usage_records_user_id", TABLE_NAME, ["user_id"], schema=SCHEMA)
    op.create_index("ix_compute_usage_records_business_type", TABLE_NAME, ["business_type"], schema=SCHEMA)
    op.create_index("ix_compute_usage_records_completed_at", TABLE_NAME, ["completed_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_compute_usage_records_completed_at", table_name=TABLE_NAME, schema=SCHEMA)
    op.drop_index("ix_compute_usage_records_business_type", table_name=TABLE_NAME, schema=SCHEMA)
    op.drop_index("ix_compute_usage_records_user_id", table_name=TABLE_NAME, schema=SCHEMA)
    op.drop_table(TABLE_NAME, schema=SCHEMA)
