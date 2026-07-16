"""normalize DeepSeek model names for the official API

Revision ID: 018
Revises: 017
Create Date: 2026-07-16
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE zhaodan.user_profiles
            SET model_name = regexp_replace(model_name, '^deepseek-ai/', '')
            WHERE model_name IN (
                'deepseek-ai/deepseek-v4-pro',
                'deepseek-ai/deepseek-v4-flash'
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE zhaodan.user_profiles
            SET model_name = 'deepseek-ai/' || model_name
            WHERE model_name IN ('deepseek-v4-pro', 'deepseek-v4-flash')
            """
        )
    )
