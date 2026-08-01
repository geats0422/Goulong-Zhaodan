"""add idempotency keys to compute usage records

Revision ID: 027
Revises: 026
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "compute_usage_records",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        schema="zhaodan",
    )
    op.create_index(
        "uq_compute_usage_user_idempotency",
        "compute_usage_records",
        ["user_id", "idempotency_key"],
        unique=True,
        schema="zhaodan",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_compute_usage_user_idempotency",
        table_name="compute_usage_records",
        schema="zhaodan",
    )
    op.drop_column("compute_usage_records", "idempotency_key", schema="zhaodan")
