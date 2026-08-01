"""persist all rule package keys used by an inspection report

Revision ID: 030
Revises: 029
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: str | None = "029"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"


def upgrade() -> None:
    op.add_column(
        "inspection_records",
        sa.Column("rule_package_keys_snapshot", sa.JSON(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("inspection_records", "rule_package_keys_snapshot", schema=SCHEMA)
