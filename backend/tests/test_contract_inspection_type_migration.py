from __future__ import annotations

from app.models import Base, InspectionRecord, KnowledgeDocument


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
    }
    index_names = {index.name for index in table.indexes}
    assert {
        "uq_inspection_types_system_key",
        "uq_inspection_types_system_name",
        "uq_inspection_types_user_key",
        "uq_inspection_types_user_name",
    } <= index_names


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


def test_migration_has_single_parent_and_preserves_legacy_scenario() -> None:
    from alembic import script
    from alembic.config import Config

    config = Config("alembic.ini")
    directory = script.ScriptDirectory.from_config(config)
    revision = directory.get_revision("025")

    assert revision.down_revision == "024"
    assert "application_scenario" in KnowledgeDocument.__table__.c
