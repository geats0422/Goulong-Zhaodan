from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class ScopeTemplateMeta:
    """权限模板元数据 — 展示层与校验层的单一数据源。"""

    key: str
    label: str
    description: str
    scopes: list[str]


SCOPE_TEMPLATES_META: list[ScopeTemplateMeta] = [
    ScopeTemplateMeta(
        key="mcp_readonly",
        label="MCP 只读",
        description="仅查询历史报告与知识库，不可体检",
        scopes=["profile:read", "inspection:read", "knowledge:read"],
    ),
    ScopeTemplateMeta(
        key="mcp_inspect",
        label="MCP 体检",
        description="能体检 + 查询，不可写知识库",
        scopes=["profile:read", "inspection:run", "inspection:read", "knowledge:read"],
    ),
    ScopeTemplateMeta(
        key="cli_review",
        label="CLI 审查",
        description="查询 + AI 体检，适用于 CLI 工具",
        scopes=["profile:read", "inspection:run", "inspection:read", "knowledge:read"],
    ),
    ScopeTemplateMeta(
        key="agent_automation",
        label="Agent 自动化",
        description="完整业务自动化，含读写与 AI 体检",
        scopes=["profile:read", "inspection:run", "inspection:read", "knowledge:read", "knowledge:write"],
    ),
]

SCOPE_TEMPLATES: dict[str, list[str]] = {m.key: list(m.scopes) for m in SCOPE_TEMPLATES_META}

_TEMPLATE_ALIASES: dict[str, str] = {
    "cli_inspection": "cli_review",
}

_CUSTOM_TEMPLATES: frozenset[str] = frozenset({"custom", "advanced_custom"})


def resolve_scopes(template_name: str, user_scopes: list[str] | None = None) -> list[str]:
    if template_name in _CUSTOM_TEMPLATES:
        if not user_scopes:
            raise ValueError("custom template requires user_scopes")
        invalid = [s for s in user_scopes if s not in ALL_SCOPES]
        if invalid:
            raise ValueError(f"invalid scopes: {invalid}")
        return list(user_scopes)

    resolved = _TEMPLATE_ALIASES.get(template_name, template_name)
    if resolved not in SCOPE_TEMPLATES:
        raise ValueError(f"unknown template: {template_name}")
    return list(SCOPE_TEMPLATES[resolved])
