"""add knowledge ownership and scenario

Revision ID: 005
Revises: 004
Create Date: 2026-06-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: str | None = "004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("owner_type", sa.String(length=20), nullable=False, server_default="user"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("application_scenario", sa.String(length=20), nullable=False, server_default="bidding"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("source_path", sa.String(length=1000), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_documents_owner_user_id_users",
        "knowledge_documents",
        "users",
        ["owner_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_knowledge_documents_owner_scenario",
        "knowledge_documents",
        ["owner_type", "owner_user_id", "application_scenario"],
    )
    op.create_unique_constraint(
        "uq_knowledge_documents_source_path",
        "knowledge_documents",
        ["source_path"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_knowledge_documents_source_path", "knowledge_documents", type_="unique")
    op.drop_index("ix_knowledge_documents_owner_scenario", table_name="knowledge_documents")
    op.drop_constraint(
        "fk_knowledge_documents_owner_user_id_users",
        "knowledge_documents",
        type_="foreignkey",
    )
    op.drop_column("knowledge_documents", "source_path")
    op.drop_column("knowledge_documents", "application_scenario")
    op.drop_column("knowledge_documents", "owner_user_id")
    op.drop_column("knowledge_documents", "owner_type")
