"""goulong-auth schema migration

Revision ID: 013
Revises: 012
Create Date: 2026-06-12

将 users / refresh_tokens 移入 goulong_auth schema，
创建 memberships 表，改造 user_profiles 移除订阅/配额字段，
所有 FK 改为引用 goulong_auth.users.id。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. 创建 goulong_auth schema
    op.execute("CREATE SCHEMA IF NOT EXISTS goulong_auth")

    # 2. 检查 goulong_auth.users 是否已存在（文衡/goulong-auth 先迁移时创建）
    auth_users_exists = bind.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_schema='goulong_auth' AND table_name='users'")
    ).scalar() is not None

    if auth_users_exists:
        # goulong_auth.users 已存在，删除本地 public.users / public.refresh_tokens
        # 先删所有指向 public.users 的 FK
        for _t, _c in [
            ("user_profiles", "user_id"), ("api_keys", "user_id"),
            ("refresh_tokens", "user_id"), ("knowledge_document_settings", "user_id"),
            ("inspection_records", "user_id"), ("taboo_words", "user_id"),
            ("agent_jobs", "user_id"), ("knowledge_documents", "owner_user_id"),
        ]:
            op.execute(f"ALTER TABLE {_t} DROP CONSTRAINT IF EXISTS {_t}_{_c}_fkey")
        op.execute("ALTER TABLE agent_jobs DROP CONSTRAINT IF EXISTS agent_jobs_api_key_id_fkey")
        op.execute("DROP TABLE IF EXISTS refresh_tokens")
        op.execute("DROP TABLE IF EXISTS users")
    else:
        # 2. 将 users 表移入 goulong_auth schema
        op.execute("ALTER TABLE users SET SCHEMA goulong_auth")
        # 3. 将 refresh_tokens 表移入 goulong_auth schema
        op.execute("ALTER TABLE refresh_tokens SET SCHEMA goulong_auth")

    # 4. 创建 memberships 表（在 goulong_auth schema）
    op.execute("""
        CREATE TABLE IF NOT EXISTS goulong_auth.memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES goulong_auth.users(id) ON DELETE CASCADE,
            product VARCHAR(20) NOT NULL,
            plan VARCHAR(20) NOT NULL DEFAULT 'free',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            token_quota INTEGER NOT NULL DEFAULT 0,
            token_used INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id, product)
        )
    """)

    # 5. 迁移数据：user_profiles 的订阅/配额 → memberships
    #    仅当本地 users 表还存在（非共享 schema 场景）时执行，
    #    否则 user_profiles.user_id 与 goulong_auth.users 不匹配会 FK 报错
    if not auth_users_exists:
        op.execute("""
            INSERT INTO goulong_auth.memberships (user_id, product, plan, status, token_quota, token_used, started_at)
            SELECT user_id, 'zhaodan',
                   COALESCE(subscription_plan, 'free'),
                   'active',
                   COALESCE(monthly_quota, 50),
                   COALESCE(quota_used, 0),
                   COALESCE(created_at, now())
            FROM user_profiles
            ON CONFLICT (user_id, product) DO NOTHING
        """)

    # 6. 改造 user_profiles：移除订阅/配额相关列
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS subscription_plan")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS monthly_quota")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS quota_used")

    # 7. 重建 FK：所有引用 users.id 的 FK 改为引用 goulong_auth.users.id
    # user_profiles
    op.execute("""
        ALTER TABLE user_profiles
        DROP CONSTRAINT IF EXISTS user_profiles_user_id_fkey,
        ADD CONSTRAINT user_profiles_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)

    # api_keys
    op.execute("""
        ALTER TABLE api_keys
        DROP CONSTRAINT IF EXISTS api_keys_user_id_fkey,
        ADD CONSTRAINT api_keys_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)

    # taboo_words
    op.execute("""
        ALTER TABLE taboo_words
        DROP CONSTRAINT IF EXISTS taboo_words_user_id_fkey,
        ADD CONSTRAINT taboo_words_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)

    # knowledge_document_settings
    op.execute("""
        ALTER TABLE knowledge_document_settings
        DROP CONSTRAINT IF EXISTS knowledge_document_settings_user_id_fkey,
        ADD CONSTRAINT knowledge_document_settings_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)

    # inspection_records
    op.execute("""
        ALTER TABLE inspection_records
        DROP CONSTRAINT IF EXISTS inspection_records_user_id_fkey,
        ADD CONSTRAINT inspection_records_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)

    # agent_jobs
    op.execute("""
        ALTER TABLE agent_jobs
        DROP CONSTRAINT IF EXISTS agent_jobs_user_id_fkey,
        ADD CONSTRAINT agent_jobs_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)

    # agent_jobs.api_key_id → api_keys.id (users 表移动后 FK 可能被错误指向)
    op.execute("""
        ALTER TABLE agent_jobs
        DROP CONSTRAINT IF EXISTS agent_jobs_api_key_id_fkey,
        ADD CONSTRAINT agent_jobs_api_key_id_fkey
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
    """)

    # knowledge_documents (owner_user_id, nullable)
    op.execute("""
        ALTER TABLE knowledge_documents
        DROP CONSTRAINT IF EXISTS knowledge_documents_owner_user_id_fkey,
        ADD CONSTRAINT knowledge_documents_owner_user_id_fkey
            FOREIGN KEY (owner_user_id) REFERENCES goulong_auth.users(id)
    """)

    # 8. 刷新令牌的 FK 已经随表移动，需要在 goulong_auth schema 内重建
    op.execute("""
        ALTER TABLE goulong_auth.refresh_tokens
        DROP CONSTRAINT IF EXISTS refresh_tokens_user_id_fkey,
        ADD CONSTRAINT refresh_tokens_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES goulong_auth.users(id) ON DELETE CASCADE
    """)


def downgrade() -> None:
    raise NotImplementedError(
        "013 downgrade 不支持自动还原。"
        "请从备份恢复或重新运行全量迁移。"
    )
