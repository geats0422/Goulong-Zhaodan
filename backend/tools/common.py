"""通用合规工具"""
from __future__ import annotations

from pydantic_ai import RunContext

from deps import InspectionDeps
from tools.base import ActionCategory, compliance_tool


@compliance_tool(
    risk_level="low",
    category=ActionCategory.QUERY,
    regulation_refs=["GB50300-2013"],
)
async def query_regulation(
    ctx: RunContext[InspectionDeps],
    regulation_name: str,
) -> str:
    """查询法规条文信息"""
    return f"法规 '{regulation_name}' 查询结果：该法规适用于当前项目类型。"


@compliance_tool(
    risk_level="medium",
    category=ActionCategory.REVIEW,
    regulation_refs=["《招标投标法》"],
)
async def check_bidding_compliance(
    ctx: RunContext[InspectionDeps],
    bidding_text: str,
) -> str:
    """检查招投标文档合规性"""
    return f"招投标文档合规性检查结果：{bidding_text[:100]}..."


@compliance_tool(
    risk_level="medium",
    category=ActionCategory.REVIEW,
    regulation_refs=["《合同法》"],
)
async def check_contract_compliance(
    ctx: RunContext[InspectionDeps],
    contract_text: str,
) -> str:
    """检查合同文档合规性"""
    return f"合同文档合规性检查结果：{contract_text[:100]}..."
