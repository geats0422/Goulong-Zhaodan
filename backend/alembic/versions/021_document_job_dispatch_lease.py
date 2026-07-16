"""add reliable document dispatch and independent leases

Revision ID: 021
Revises: 020
Create Date: 2026-07-16
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "021"
down_revision: str | None = "020"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"
TABLE = "document_processing_jobs"


def upgrade() -> None:
    columns = (
        sa.Column("dispatch_pending", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("dispatch_retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("dispatch_claim_owner", sa.String(length=100), nullable=True),
        sa.Column("dispatch_claim_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in columns:
        op.add_column(TABLE, column, schema=SCHEMA)
    op.execute(
        sa.text(
            "UPDATE zhaodan.document_processing_jobs "
            "SET dispatch_pending = false "
            "WHERE status IN ('succeeded', 'failed', 'cancelled')"
        )
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_dispatch_retry_nonnegative",
        TABLE,
        "dispatch_retry_count >= 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_dispatch_claim_pair",
        TABLE,
        "(dispatch_claim_owner IS NULL) = (dispatch_claim_expires_at IS NULL)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_document_processing_jobs_lease_pair",
        TABLE,
        "(lease_owner IS NULL) = (lease_expires_at IS NULL)",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_document_processing_jobs_dispatch_pending",
        TABLE,
        ["dispatch_pending", "next_dispatch_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("dispatch_pending"),
    )
    op.create_index(
        "ix_document_processing_jobs_expired_lease",
        TABLE,
        ["status", "lease_expires_at"],
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("ix_document_processing_jobs_expired_lease", table_name=TABLE, schema=SCHEMA)
    op.drop_index("ix_document_processing_jobs_dispatch_pending", table_name=TABLE, schema=SCHEMA)
    for name in (
        "ck_document_processing_jobs_lease_pair",
        "ck_document_processing_jobs_dispatch_claim_pair",
        "ck_document_processing_jobs_dispatch_retry_nonnegative",
    ):
        op.drop_constraint(name, TABLE, type_="check", schema=SCHEMA)
    for column in (
        "lease_expires_at",
        "lease_owner",
        "dispatch_claim_expires_at",
        "dispatch_claim_owner",
        "next_dispatch_at",
        "dispatch_retry_count",
        "dispatch_pending",
    ):
        op.drop_column(TABLE, column, schema=SCHEMA)
