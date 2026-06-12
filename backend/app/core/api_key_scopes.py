from __future__ import annotations

ALL_SCOPES: tuple[str, ...] = (
    "profile:read",
    "inspection:run",
    "inspection:read",
    "knowledge:read",
    "knowledge:write",
    "settings:write",
    "records:delete",
)

AVAILABLE_SCOPES: tuple[str, ...] = tuple(s for s in ALL_SCOPES if s != "records:delete")

CLIENT_TYPES: tuple[str, ...] = ("mcp", "cli", "skill", "agent", "other")

SCOPE_TEMPLATES: dict[str, list[str]] = {
    "mcp_readonly": [
        "profile:read",
        "inspection:read",
        "knowledge:read",
    ],
    "cli_inspection": [
        "profile:read",
        "inspection:run",
        "inspection:read",
        "knowledge:read",
    ],
    "agent_automation": [
        "profile:read",
        "inspection:run",
        "inspection:read",
        "knowledge:read",
        "knowledge:write",
    ],
}


def resolve_scopes(template_name: str, user_scopes: list[str] | None = None) -> list[str]:
    if template_name == "custom":
        if not user_scopes:
            raise ValueError("custom template requires user_scopes")
        invalid = [s for s in user_scopes if s not in ALL_SCOPES]
        if invalid:
            raise ValueError(f"invalid scopes: {invalid}")
        return list(user_scopes)

    if template_name not in SCOPE_TEMPLATES:
        raise ValueError(f"unknown template: {template_name}")

    return list(SCOPE_TEMPLATES[template_name])
