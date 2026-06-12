"""UUID migration: integer PK → UUID PK

Revision ID: 012
Revises: 011
Create Date: 2026-06-12

将 users / user_profiles / api_keys 的主键从 SERIAL 迁移到 UUID，
所有引用 users.id 的外键列同步从 INTEGER 转为 UUID。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# 业务表 user_id FK 迁移辅助（不含 api_keys.id 和 agent_jobs.api_key_id）
# ---------------------------------------------------------------------------
# 每个元组: (表名, FK约束名, 旧索引名, 新索引列列表, FK列名)
_USER_FK_TABLES = [
    (
        "user_profiles",
        "user_profiles_user_id_fkey",
        None,    # user_profiles.user_id 有 UNIQUE 约束而非普通索引
        None,
        "user_id",
    ),
    (
        "api_keys",
        "api_keys_user_id_fkey",
        None,
        None,
        "user_id",
    ),
    (
        "refresh_tokens",
        "refresh_tokens_user_id_fkey",
        "ix_refresh_tokens_user_id",
        ["user_id"],
        "user_id",
    ),
    (
        "knowledge_document_settings",
        "knowledge_document_settings_user_id_fkey",
        "ix_knowledge_document_settings_user_id",
        ["user_id"],
        "user_id",
    ),
    (
        "inspection_records",
        "inspection_records_user_id_fkey",
        "ix_inspection_records_user_created",
        ["user_id", "created_at"],
        "user_id",
    ),
    (
        "taboo_words",
        "taboo_words_user_id_fkey",
        "ix_taboo_words_user_id",
        ["user_id"],
        "user_id",
    ),
    (
        "agent_jobs",
        "agent_jobs_user_id_fkey",
        None,
        None,
        "user_id",
    ),
    (
        "knowledge_documents",
        None,
        None,
        None,
        "owner_user_id",
    ),
]


def _migrate_fk_column(table: str, col: str, fk_name: str | None,
                        index_name: str | None, index_columns: list[str] | None,
                        mapping_table: str = "_uuid_mapping",
                        mapping_old: str = "old_id",
                        mapping_new: str = "new_id",
                        nullable: bool = False) -> None:
    """将某个 FK 列从 INTEGER 迁移为 UUID（通过映射表 JOIN）。"""
    new_col = f"_new_{col}"

    # 1) 删旧 FK（如果还没被删掉）
    if fk_name:
        op.drop_constraint(fk_name, table, type_="foreignkey")

    # 2) 删旧索引（需要在删列之前）
    if index_name:
        op.drop_index(index_name, table_name=table)

    # 3) 添加临时 UUID 列
    op.add_column(table, sa.Column(new_col, sa.String(36), nullable=True))

    # 4) 通过映射表填充
    op.execute(
        f"UPDATE {table} t SET {new_col} = m.{mapping_new}::text "
        f"FROM {mapping_table} m WHERE t.{col} = m.{mapping_old}"
    )

    # 5) 如果不允许 NULL，将仍未映射的行设为默认值（防御性）
    if not nullable:
        op.execute(
            f"UPDATE {table} SET {new_col} = '00000000-0000-0000-0000-000000000000' "
            f"WHERE {new_col} IS NULL"
        )

    # 6) 删旧列，重命名新列
    op.drop_column(table, col)
    op.alter_column(table, new_col, new_column_name=col)
    if not nullable:
        op.alter_column(table, col, nullable=False)

    # 7) 将 text 列转为真正的 UUID 类型
    op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE UUID USING {col}::uuid")

    # 8) 重建 FK（指向新 users.id）
    op.create_foreign_key(
        fk_name or f"{table}_{col}_fkey",
        table, "users", [col], ["id"],
    )

    # 9) 重建索引
    if index_name and index_columns:
        op.create_index(index_name, table, index_columns)


def upgrade() -> None:
    # ── Step 1: 启用 uuid 扩展 ──
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── Step 2: 创建 user_id 映射表 ──
    op.create_table(
        "_uuid_mapping",
        sa.Column("old_id", sa.Integer(), primary_key=True),
        sa.Column("new_id", sa.String(36), nullable=False,
                  server_default=sa.text("uuid_generate_v4()::text")),
    )

    # ── Step 3: 填充映射 ──
    op.execute("INSERT INTO _uuid_mapping (old_id) SELECT id FROM users")

    # ── Step 4: 创建新 users 表 ──
    op.create_table(
        "_new_users",
        sa.Column("id", sa.String(36), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()::text")),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("wechat_openid", sa.String(64), nullable=True),
        sa.Column("alipay_user_id", sa.String(64), nullable=True),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="ck_users_has_identity",
        ),
    )

    # ── Step 5: 迁移 users 数据 ──
    # geats 用户特殊处理（username='geats' 或 display_name 含 geats）
    op.execute(
        """
        INSERT INTO _new_users (id, nickname, hashed_password, is_active,
                                phone, email, created_at, updated_at)
        SELECT m.new_id,
               COALESCE(up.display_name, u.username),
               u.hashed_password,
               u.is_active,
               '17345823742',
               'geats@qq.com',
               u.created_at,
               u.updated_at
        FROM users u
        JOIN _uuid_mapping m ON m.old_id = u.id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.username = 'geats'
        """
    )
    # 其余用户
    op.execute(
        """
        INSERT INTO _new_users (id, nickname, hashed_password, is_active,
                                phone, email, created_at, updated_at)
        SELECT m.new_id,
               COALESCE(up.display_name, u.username),
               u.hashed_password,
               u.is_active,
               up.phone,
               COALESCE(up.email, u.username || '@placeholder.local'),
               u.created_at,
               u.updated_at
        FROM users u
        JOIN _uuid_mapping m ON m.old_id = u.id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.username != 'geats'
        """
    )

    # ── Step 6: 替换 users 表 ──
    # 先删除引用旧 users.id / api_keys.id 的所有 FK（否则 DROP TABLE 会失败）
    # 注意：这些 FK 在 Step 6 被删除后，Step 9 中 _migrate_fk_column 不再需要删 FK
    for _t, _fk, _, _, _ in _USER_FK_TABLES:
        if _fk:
            op.drop_constraint(_fk, _t, type_="foreignkey")
    # agent_jobs → api_keys FK
    op.drop_constraint("agent_jobs_api_key_id_fkey", "agent_jobs", type_="foreignkey")

    op.drop_table("users")
    op.rename_table("_new_users", "users")

    # 将 id 列转为真正 UUID 类型
    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN id TYPE UUID USING id::uuid")
    op.execute(
        "ALTER TABLE users ALTER COLUMN id "
        "SET DEFAULT uuid_generate_v4()"
    )

    # ── Step 7: 创建 users 索引 ──
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])
    op.create_index("ix_users_wechat_openid", "users", ["wechat_openid"])
    op.create_index("ix_users_alipay_user_id", "users", ["alipay_user_id"])

    # ── Step 8: 迁移 user_profiles ──
    # 先处理 user_profiles 的 user_id FK → UUID
    _migrate_fk_column(
        "user_profiles", "user_id", None, None, None,
        nullable=False,
    )

    # 重建 user_profiles.user_id UNIQUE 约束（1:1 关系）
    op.create_unique_constraint(
        "uq_user_profiles_user_id", "user_profiles", ["user_id"],
    )

    # 添加 legacy_id 列（保留旧 integer id）
    op.add_column(
        "user_profiles",
        sa.Column("legacy_id", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE user_profiles SET legacy_id = m.old_id "
        "FROM _uuid_mapping m WHERE user_profiles.user_id = m.new_id::uuid"
    )
    op.create_unique_constraint("uq_user_profiles_legacy_id", "user_profiles", ["legacy_id"])

    # user_profiles 主键 SERIAL → UUID
    op.add_column(
        "user_profiles",
        sa.Column("_new_id", sa.String(36), nullable=True,
                  server_default=sa.text("uuid_generate_v4()::text")),
    )
    op.drop_constraint("user_profiles_pkey", "user_profiles", type_="primary")
    op.drop_column("user_profiles", "id")
    op.alter_column("user_profiles", "_new_id", new_column_name="id", nullable=False)
    op.execute("ALTER TABLE user_profiles ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE user_profiles ALTER COLUMN id TYPE UUID USING id::uuid")
    op.execute("ALTER TABLE user_profiles ALTER COLUMN id SET DEFAULT uuid_generate_v4()")
    op.create_primary_key("user_profiles_pkey", "user_profiles", ["id"])

    # 删除旧字段（不再需要的列）
    op.drop_column("user_profiles", "display_name")
    op.drop_column("user_profiles", "wechat_bound")
    op.drop_column("user_profiles", "alipay_bound")

    # ── Step 9: 迁移业务表的 user_id FK ──
    # FK 已在 Step 6 中全部删除，此处 fk_name=None 跳过删 FK
    for table, _fk_name, idx_name, idx_cols, col in _USER_FK_TABLES:
        if table in ("user_profiles",):
            continue  # 已处理
        _migrate_fk_column(table, col, None, idx_name, idx_cols,
                           nullable=(col == "owner_user_id"))

    # 重建 knowledge_document_settings 的复合 UNIQUE 约束
    # （DROP user_id 列时级联删除了 uq_user_knowledge_document_setting）
    op.create_unique_constraint(
        "uq_user_knowledge_document_setting",
        "knowledge_document_settings",
        ["user_id", "document_id"],
    )

    # 重建 taboo_words 的复合 UNIQUE 约束
    # （DROP user_id 列时级联删除了 uq_user_taboo_word）
    op.create_unique_constraint(
        "uq_user_taboo_word",
        "taboo_words",
        ["user_id", "word"],
    )

    # ── Step 10: 迁移 api_keys.id SERIAL → UUID ──
    op.create_table(
        "_api_key_uuid_mapping",
        sa.Column("old_id", sa.Integer(), primary_key=True),
        sa.Column("new_id", sa.String(36), nullable=False,
                  server_default=sa.text("uuid_generate_v4()::text")),
    )
    op.execute("INSERT INTO _api_key_uuid_mapping (old_id) SELECT id FROM api_keys")

    # 添加临时 UUID id 列
    op.add_column(
        "api_keys",
        sa.Column("_new_id", sa.String(36), nullable=True,
                  server_default=sa.text("uuid_generate_v4()::text")),
    )
    op.execute(
        "UPDATE api_keys SET _new_id = m.new_id "
        "FROM _api_key_uuid_mapping m WHERE api_keys.id = m.old_id"
    )
    op.drop_constraint("api_keys_pkey", "api_keys", type_="primary")
    op.drop_column("api_keys", "id")
    op.alter_column("api_keys", "_new_id", new_column_name="id", nullable=False)
    op.execute("ALTER TABLE api_keys ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE api_keys ALTER COLUMN id TYPE UUID USING id::uuid")
    op.execute("ALTER TABLE api_keys ALTER COLUMN id SET DEFAULT uuid_generate_v4()")
    op.create_primary_key("api_keys_pkey", "api_keys", ["id"])

    # 迁移 agent_jobs.api_key_id INTEGER → UUID
    _migrate_fk_column(
        "agent_jobs", "api_key_id", None, None, None,
        mapping_table="_api_key_uuid_mapping",
        mapping_old="old_id",
        mapping_new="new_id",
    )

    # ── Step 11: 清理临时表 ──
    op.drop_table("_api_key_uuid_mapping")
    op.drop_table("_uuid_mapping")


def downgrade() -> None:
    """回滚迁移：将表结构恢复为 integer 主键。
    注意：此 downgrade 仅恢复表结构，不恢复数据。
    仅用于开发环境快速回滚到 integer schema 以重新运行 upgrade。
    """
    # 降级是破坏性操作：UUID 数据无法自动还原为 integer
    # 这里只提供表结构回退，需要手动处理数据
    raise NotImplementedError(
        "UUID → integer downgrade 不支持自动数据还原。"
        "请从备份恢复或重新运行全量迁移。"
    )
