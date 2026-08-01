from __future__ import annotations

import os
from pathlib import Path
import uuid

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

from app.models import Base, InspectionRecord, KnowledgeDocument

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_contract_inspection_types_table_defines_two_dimensions_and_user_scope() -> None:
    table = Base.metadata.tables["zhaodan.inspection_types"]

    assert {column.name for column in table.columns} == {
        "id",
        "key",
        "name",
        "dimension",
        "owner_type",
        "owner_user_id",
        "enabled",
        "created_at",
        "updated_at",
    }
    assert {constraint.name for constraint in table.constraints} >= {
        "ck_inspection_types_dimension",
        "ck_inspection_types_owner_type",
        "ck_inspection_types_owner_scope",
        "ck_inspection_types_enabled",
    }
    index_names = {index.name for index in table.indexes}
    assert {
        "uq_inspection_types_system_key",
        "uq_inspection_types_system_name",
        "uq_inspection_types_user_key",
        "uq_inspection_types_user_name",
    } <= index_names
    assert table.c.enabled.server_default is not None
    assert table.c.created_at.server_default is not None
    assert table.c.updated_at.server_default is not None

    predicates = {
        index.name: str(index.dialect_options["postgresql"].get("where"))
        for index in table.indexes
    }
    assert "owner_type" in predicates["uq_inspection_types_system_key"]
    assert "owner_type" in predicates["uq_inspection_types_user_key"]


def test_knowledge_and_inspection_models_expose_contract_classification_snapshots() -> None:
    knowledge_columns = KnowledgeDocument.__table__.c
    assert knowledge_columns.engineering_type_key.nullable
    assert knowledge_columns.contract_type_key.nullable
    assert not knowledge_columns.is_active.nullable

    inspection_columns = InspectionRecord.__table__.c
    for name in (
        "detected_engineering_type",
        "final_engineering_type",
        "detected_contract_type",
        "final_contract_type",
        "classification_confidence",
        "rule_package_key",
        "classification_source",
        "engineering_type_snapshot",
        "contract_type_snapshot",
        "knowledge_sources_snapshot",
    ):
        assert inspection_columns[name].nullable
    assert {
        "ck_inspection_records_classification_confidence",
        "ck_inspection_records_classification_source",
    } <= {constraint.name for constraint in InspectionRecord.__table__.constraints}
    assert knowledge_columns.is_active.server_default is not None


def test_migration_has_single_parent_and_preserves_legacy_scenario() -> None:
    from alembic import script
    from alembic.config import Config

    config = Config("alembic.ini")
    directory = script.ScriptDirectory.from_config(config)
    revision = directory.get_revision("025")

    assert revision.down_revision == "024"
    assert "application_scenario" in KnowledgeDocument.__table__.c


def _validated_test_url() -> URL:
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if raw_url is None:
        from app.core.config import settings

        configured_url = make_url(settings.database_url)
        raw_url = configured_url.set(
            host="127.0.0.1" if configured_url.host == "localhost" else configured_url.host,
            database="goulong_test",
        ).render_as_string(hide_password=False)
    url = make_url(raw_url.replace("+asyncpg", ""))
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise RuntimeError("合同初审迁移测试必须使用名称以 _test 结尾的 PostgreSQL 测试库")
    return url


def _migration_config(database_url: URL) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.render_as_string(hide_password=False))
    return config


def test_real_postgres_upgrade_downgrade_and_reupgrade_preserves_legacy_rows() -> None:
    source_url = _validated_test_url()
    database_name = f"goulong_contract_types_{uuid.uuid4().hex[:8]}_test"
    admin_engine = create_engine(source_url, isolation_level="AUTOCOMMIT")
    target_engine = None

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        target_url = source_url.set(database=database_name)
        target_engine = create_engine(target_url)
        user_id = uuid.uuid4()
        with target_engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA goulong_auth"))
            connection.execute(text("CREATE SCHEMA zhaodan"))
            connection.execute(text("CREATE TABLE goulong_auth.users (id UUID PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE zhaodan.knowledge_documents (id SERIAL PRIMARY KEY, application_scenario VARCHAR(20) NOT NULL)"))
            connection.execute(text("CREATE TABLE zhaodan.inspection_records (id SERIAL PRIMARY KEY)"))
            connection.execute(text("INSERT INTO goulong_auth.users (id) VALUES (:id)"), {"id": user_id})
            connection.execute(text("INSERT INTO zhaodan.knowledge_documents (application_scenario) VALUES ('bidding')"))
            connection.execute(text("INSERT INTO zhaodan.inspection_records DEFAULT VALUES"))

        config = _migration_config(target_url)
        command.stamp(config, "024")
        command.upgrade(config, "025")
        inspector = inspect(target_engine)
        knowledge = inspector.get_columns("knowledge_documents", schema="zhaodan")
        assert next(column for column in knowledge if column["name"] == "is_active")["default"] in {"true", "TRUE"}
        inspection_type_columns = inspector.get_columns("inspection_types", schema="zhaodan")
        assert {column["name"] for column in inspection_type_columns} >= {"enabled", "created_at", "updated_at"}
        assert next(column for column in inspection_type_columns if column["name"] == "enabled")["default"] in {"true", "TRUE"}
        assert {
            "ck_inspection_types_dimension",
            "ck_inspection_types_owner_type",
            "ck_inspection_types_owner_scope",
            "ck_inspection_types_enabled",
            "ck_inspection_records_classification_confidence",
            "ck_inspection_records_classification_source",
        } <= {
            constraint["name"]
            for table_name in ("inspection_types", "inspection_records")
            for constraint in inspector.get_check_constraints(table_name, schema="zhaodan")
        }
        assert any(
            foreign_key["referred_table"] == "users"
            and foreign_key["referred_schema"] == "goulong_auth"
            for foreign_key in inspector.get_foreign_keys("inspection_types", schema="zhaodan")
        )
        partial_indexes = {
            index["name"]: index.get("dialect_options", {}).get("postgresql_where", "")
            for index in inspector.get_indexes("inspection_types", schema="zhaodan")
        }
        assert "owner_type" in partial_indexes["uq_inspection_types_system_key"]
        assert "owner_type" in partial_indexes["uq_inspection_types_user_key"]
        with target_engine.connect() as connection:
            assert connection.execute(text("SELECT application_scenario FROM zhaodan.knowledge_documents")).scalar_one() == "bidding"
            assert connection.execute(text("SELECT is_active FROM zhaodan.knowledge_documents")).scalar_one() is True
        assert {index["name"] for index in inspector.get_indexes("inspection_types", schema="zhaodan")} >= {
            "uq_inspection_types_system_key",
            "uq_inspection_types_user_key",
        }

        command.downgrade(config, "024")
        inspector.clear_cache()
        assert not inspector.has_table("inspection_types", schema="zhaodan")
        assert "is_active" not in {column["name"] for column in inspector.get_columns("knowledge_documents", schema="zhaodan")}
        command.upgrade(config, "025")
        inspector.clear_cache()
        assert inspector.has_table("inspection_types", schema="zhaodan")
    finally:
        if target_engine is not None:
            target_engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :database_name"),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()
