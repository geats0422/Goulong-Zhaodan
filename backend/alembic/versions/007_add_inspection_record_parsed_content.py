"""add inspection record parsed content

Revision ID: 007
Revises: 006
Create Date: 2026-06-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspection_records",
        sa.Column("parsed_content", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("inspection_records", "parsed_content", server_default=None)


def downgrade() -> None:
    op.drop_column("inspection_records", "parsed_content")
