from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "markitdown",
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

from core.api_key_scopes import (
    ALL_SCOPES,
    AVAILABLE_SCOPES,
    CLIENT_TYPES,
    SCOPE_TEMPLATES,
    resolve_scopes,
)


EXPECTED_ALL_SCOPES = {
    "profile:read",
    "inspection:run",
    "inspection:read",
    "knowledge:read",
    "knowledge:write",
    "settings:write",
    "records:delete",
}


def test_all_scopes_contains_seven_entries():
    assert len(ALL_SCOPES) == 7


def test_all_scopes_has_expected_values():
    assert set(ALL_SCOPES) == EXPECTED_ALL_SCOPES


def test_available_scopes_excludes_records_delete():
    assert "records:delete" not in AVAILABLE_SCOPES
    assert "records:delete" in ALL_SCOPES


def test_available_scopes_is_subset_of_all_scopes():
    assert set(AVAILABLE_SCOPES).issubset(set(ALL_SCOPES))


def test_client_types_contains_expected_values():
    expected = {"mcp", "cli", "skill", "agent", "other"}
    assert set(CLIENT_TYPES) == expected


def test_scope_template_mcp_readonly():
    template = SCOPE_TEMPLATES["mcp_readonly"]
    assert set(template) == {"profile:read", "inspection:read", "knowledge:read"}


def test_scope_template_cli_inspection():
    template = SCOPE_TEMPLATES["cli_inspection"]
    assert set(template) == {
        "profile:read",
        "inspection:run",
        "inspection:read",
        "knowledge:read",
    }


def test_scope_template_agent_automation():
    template = SCOPE_TEMPLATES["agent_automation"]
    assert set(template) == {
        "profile:read",
        "inspection:run",
        "inspection:read",
        "knowledge:read",
        "knowledge:write",
    }


def test_scope_template_custom_not_exists_or_empty():
    custom = SCOPE_TEMPLATES.get("custom")
    assert custom is None or custom == []


def test_each_template_scope_is_in_all_scopes():
    for name, scopes in SCOPE_TEMPLATES.items():
        if name == "custom":
            continue
        for scope in scopes:
            assert scope in ALL_SCOPES, f"{name} 包含无效 scope: {scope}"


def test_resolve_scopes_mcp_readonly():
    result = resolve_scopes("mcp_readonly")
    assert set(result) == {"profile:read", "inspection:read", "knowledge:read"}


def test_resolve_scopes_custom_with_user_scopes():
    user_scopes = ["profile:read", "inspection:read"]
    result = resolve_scopes("custom", user_scopes=user_scopes)
    assert result == user_scopes


def test_resolve_scopes_invalid_template_raises():
    with pytest.raises((ValueError, KeyError)):
        resolve_scopes("nonexistent_template")


def test_resolve_scopes_custom_with_invalid_scope_raises():
    with pytest.raises((ValueError, KeyError)):
        resolve_scopes("custom", user_scopes=["invalid:scope"])


def test_resolve_scopes_custom_without_user_scopes_raises():
    with pytest.raises((ValueError, KeyError)):
        resolve_scopes("custom")
