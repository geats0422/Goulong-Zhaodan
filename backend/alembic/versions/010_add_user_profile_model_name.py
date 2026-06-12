from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "010"
down_revision = "009"


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("model_name", sa.String(120), nullable=True))
    try:
        from core.config import settings

        bind = op.get_bind()
        bind.execute(
            sa.text("UPDATE user_profiles SET model_name = :n WHERE model_name IS NULL"),
            {"n": settings.model_name},
        )
    except Exception:
        pass


def downgrade() -> None:
    op.drop_column("user_profiles", "model_name")
