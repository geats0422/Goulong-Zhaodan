"""add payment method to payment_orders

Revision ID: 016
Revises: 015
Create Date: 2026-07-09
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "016"
down_revision: str | None = "015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"


def upgrade() -> None:
    op.add_column(
        "payment_orders",
        sa.Column("payment_method", sa.String(20), nullable=False, server_default="wechat"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("payment_orders", "payment_method", schema=SCHEMA)
