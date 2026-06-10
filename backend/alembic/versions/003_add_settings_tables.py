"""add settings tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: str | None = "002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("subscription_plan", sa.String(length=50), nullable=False),
        sa.Column("monthly_quota", sa.Integer(), nullable=False),
        sa.Column("quota_used", sa.Integer(), nullable=False),
        sa.Column("wechat_bound", sa.Boolean(), nullable=False),
        sa.Column("alipay_bound", sa.Boolean(), nullable=False),
        sa.Column("burn_after_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "taboo_words",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("word", sa.String(length=100), nullable=False),
        sa.Column("replacement", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "word", name="uq_user_taboo_word"),
    )
    op.create_table(
        "knowledge_document_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "document_id", name="uq_user_knowledge_document_setting"),
    )
    op.create_index("ix_taboo_words_user_id", "taboo_words", ["user_id"])
    op.create_index("ix_knowledge_document_settings_user_id", "knowledge_document_settings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_document_settings_user_id", table_name="knowledge_document_settings")
    op.drop_index("ix_taboo_words_user_id", table_name="taboo_words")
    op.drop_table("knowledge_document_settings")
    op.drop_table("taboo_words")
    op.drop_table("user_profiles")
