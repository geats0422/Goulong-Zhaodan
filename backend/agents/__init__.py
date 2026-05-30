"""Agent 定义（懒加载模式）

模块导入时不初始化 Agent，首次访问时才创建，避免缺少 API Key 时导入失败。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from app.prompts.inspection_prompts import (
    COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
    INSPECTION_COORDINATOR_SYSTEM_PROMPT,
    REGULATION_ANALYST_SYSTEM_PROMPT,
)
from core.config import settings
from core.deps import InspectionDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent as AgentType


# ─── 懒加载缓存 ───
_agents: dict[str, AgentType] = {}


def get_regulation_analyst() -> AgentType:
    if "regulation_analyst" not in _agents:
        _agents["regulation_analyst"] = Agent(
            f"openai:{settings.model_name}",
            deps_type=InspectionDeps,
            output_type=str,
            instructions=REGULATION_ANALYST_SYSTEM_PROMPT,
            model_settings={"temperature": 0.0},
        )
    return _agents["regulation_analyst"]


def get_compliance_inspector() -> AgentType:
    if "compliance_inspector" not in _agents:
        _agents["compliance_inspector"] = Agent(
            f"openai:{settings.model_name}",
            deps_type=InspectionDeps,
            output_type=str,
            instructions=COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
        )
    return _agents["compliance_inspector"]


def get_inspection_agent() -> AgentType:
    if "inspection_agent" not in _agents:
        _agents["inspection_agent"] = Agent(
            f"openai:{settings.model_name}",
            deps_type=InspectionDeps,
            output_type=str,
            instructions=INSPECTION_COORDINATOR_SYSTEM_PROMPT,
        )
    return _agents["inspection_agent"]


# 模块级 __getattr__：首次访问 regulation_analyst / compliance_inspector / inspection_agent 时才初始化
def __getattr__(name: str) -> AgentType:
    if name == "regulation_analyst":
        return get_regulation_analyst()
    if name == "compliance_inspector":
        return get_compliance_inspector()
    if name == "inspection_agent":
        return get_inspection_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
