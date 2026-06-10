"""add inspection records

Revision ID: 006
Revises: 005
Create Date: 2026-06-02 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: str | None = "005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inspection_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("document_type_label", sa.String(length=50), nullable=False),
        sa.Column("project_id", sa.String(length=100), nullable=False, server_default="default"),
        sa.Column("overall_risk", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("regulation_refs", sa.JSON(), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("quota_consumed", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_inspection_records_user_id_users"),
    )
    op.create_index("ix_inspection_records_user_created", "inspection_records", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_inspection_records_user_created", table_name="inspection_records")
    op.drop_table("inspection_records")
