"""历史体检记录的只读兼容展示。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _value(record: Mapping[str, Any] | object, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def classification_display(record: Mapping[str, Any] | object) -> str:
    """为新旧记录提供稳定的历史类别文案，不触发重新分类。"""
    if (
        _value(record, "application_scenario") == "bidding"
        or _value(record, "document_type") == "bidding"
    ):
        return "历史记录 / 招投标资料已归档，无法按旧场景重审"
    if _value(record, "classification_source") == "legacy":
        return "历史记录 / 通用工程合同"
    engineering = _value(record, "engineering_type_snapshot")
    contract = _value(record, "contract_type_snapshot")
    if engineering and contract:
        return f"{engineering} / {contract}"
    return "历史记录 / 通用工程合同"


def rule_package_keys_display(record: Mapping[str, Any] | object) -> list[str]:
    """返回报告保存时使用的完整规则包快照，兼容旧单值记录。"""
    snapshot = _value(record, "rule_package_keys_snapshot")
    if isinstance(snapshot, list):
        return [str(key) for key in snapshot if str(key).strip()]
    single = _value(record, "rule_package_key")
    return [str(single)] if single else []


def is_archived_legacy_record(record: Mapping[str, Any] | object) -> bool:
    return _value(record, "application_scenario") == "bidding" or _value(
        record, "document_type"
    ) == "bidding" or _value(record, "classification_source") == "archived_legacy"
