"""replace usage idempotency uniqueness with a user-scoped constraint

Revision ID: 028
Revises: 027
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "028"
down_revision: str | None = "027"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_compute_usage_records_idempotency_key",
        table_name="compute_usage_records",
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
    op.create_index(
        "ix_compute_usage_records_idempotency_key",
        "compute_usage_records",
        ["idempotency_key"],
        unique=True,
        schema="zhaodan",
    )
