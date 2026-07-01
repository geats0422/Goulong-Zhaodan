"""add password_changed_at to goulong_auth users

Revision ID: 014
Revises: 013
Create Date: 2026-06-17 14:08:53.229360
"""
from __future__ import annotations

from typing import Sequence

from alembic import op


revision: str = '014'
down_revision: str | None = '013'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE goulong_auth.users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP WITH TIME ZONE NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE goulong_auth.users DROP COLUMN password_changed_at")
