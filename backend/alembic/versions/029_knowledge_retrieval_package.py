"""add knowledge rule package metadata and retrieval index

Revision ID: 029
Revises: 028
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: str | None = "028"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "zhaodan"


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("rule_package_key", sa.String(length=100), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_knowledge_documents_retrieval",
        "knowledge_documents",
        [
            "application_scenario",
            "is_active",
            "owner_type",
            "owner_user_id",
            "engineering_type_key",
            "contract_type_key",
            "rule_package_key",
        ],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_retrieval", table_name="knowledge_documents", schema=SCHEMA)
    op.drop_column("knowledge_documents", "rule_package_key", schema=SCHEMA)
