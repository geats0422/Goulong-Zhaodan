"""Agent 定义（懒加载模式）

模块导入时不初始化 Agent，首次访问时才创建，避免缺少 API Key 时导入失败。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from app.prompts.inspection_prompts import (
    COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
    CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
    CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT,
    INSPECTION_COORDINATOR_SYSTEM_PROMPT,
    REGULATION_ANALYST_SYSTEM_PROMPT,
)
from app.core.config import settings
from app.core.deps import InspectionDeps
from app.core.model_config import normalize_model_name

if TYPE_CHECKING:
    from pydantic_ai import Agent as AgentType


def _make_model():
    """根据 settings 创建 OpenAI 兼容模型实例。"""
    from pydantic_ai.models.openai import OpenAIModel
    from pydantic_ai.providers.openai import OpenAIProvider

    provider = OpenAIProvider(
        base_url=settings.model_base_url,
        api_key=settings.model_api_key,
    )
    return OpenAIModel(normalize_model_name(settings.model_name) or settings.model_name, provider=provider)


# ─── 懒加载缓存 ───
_agents: dict[str, AgentType] = {}


def get_regulation_analyst(scenario: str = "bidding") -> AgentType:
    cache_key = f"regulation_analyst_{scenario}"
    if cache_key not in _agents:
        instructions = (
            CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT
            if scenario == "contract"
            else REGULATION_ANALYST_SYSTEM_PROMPT
        )
        _agents[cache_key] = Agent(
            _make_model(),
            deps_type=InspectionDeps,
            output_type=str,
            instructions=instructions,
            model_settings={"temperature": 0.0},
        )
    return _agents[cache_key]


def get_compliance_inspector(scenario: str = "bidding") -> AgentType:
    cache_key = f"compliance_inspector_{scenario}"
    if cache_key not in _agents:
        instructions = (
            CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT
            if scenario == "contract"
            else COMPLIANCE_INSPECTOR_SYSTEM_PROMPT
        )
        _agents[cache_key] = Agent(
            _make_model(),
            deps_type=InspectionDeps,
            output_type=str,
            instructions=instructions,
        )
    return _agents[cache_key]


def get_inspection_agent() -> AgentType:
    if "inspection_agent" not in _agents:
        _agents["inspection_agent"] = Agent(
            _make_model(),
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
