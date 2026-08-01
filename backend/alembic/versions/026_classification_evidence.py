"""persist classification evidence and make new knowledge uploads contract-only

Revision ID: 026
Revises: 025
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: str | None = "025"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"


def upgrade() -> None:
    op.add_column(
        "inspection_records",
        sa.Column("classification_evidence", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )
    op.alter_column(
        "knowledge_documents",
        "application_scenario",
        server_default=sa.text("'contract'"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_documents",
        "application_scenario",
        server_default=sa.text("'bidding'"),
        schema=SCHEMA,
    )
    op.drop_column("inspection_records", "classification_evidence", schema=SCHEMA)
