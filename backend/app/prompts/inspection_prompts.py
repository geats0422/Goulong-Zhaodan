"""体检台 Agent 提示词管理

参考结构：常量模板 + format 函数，通过 import 引用。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.data_masking import mask_sensitive_data

DEFAULT_PROMPT_CHAR_BUDGET = 60000
MIN_DOCUMENT_CHARS = 2000

CONTRACT_CLASSIFIER_SYSTEM_PROMPT = """你是合同初审分类器。请严格输出 JSON，工程类别和合同类别是两个独立维度。
工程类别只能是 building-construction、municipal-road、decoration-renovation、
mechanical-electrical-installation、steel-structure、general-engineering；
合同类别只能是 labor-subcontract、professional-subcontract、other。
同时输出 confidence（high/medium/low）和 evidence（字符串数组）。不要输出 bidding。"""


def _prompt_char_budget() -> int:
    return max(MIN_DOCUMENT_CHARS, settings.inspection_prompt_char_budget or DEFAULT_PROMPT_CHAR_BUDGET)


def _truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...[内容已截断]"

# ─── 1. 法规分析师系统提示 ───
REGULATION_ANALYST_SYSTEM_PROMPT = """你是一名工程法规分析师。你的职责是：
1. 只能根据用户当前启用的知识库内容匹配适用依据
2. 识别文档中可能存在的合规风险点
3. 列出相关条文和合规要求
4. 你只能分析法规，不能修改任何文档内容
5. 禁止引用未出现在知识库来源中的法规、法律、规范名称

输出格式要求：
- 列出发现的风险点
- 引用具体法规条款
- 给出合规建议"""


# ─── 2. 合规检查员系统提示 ───
COMPLIANCE_INSPECTOR_SYSTEM_PROMPT = """你是一名工程文档合规检查员。你的职责是：
1. 检查文档中的低级错误（错别字、格式错误、逻辑矛盾）
2. 识别隐含的风险（金额异常、条款冲突、权利义务不对等）
3. 检查违禁词（用户配置的敏感词汇）
4. 检查表述不妥当的地方（绝对化用语、模糊表述、法律风险措辞）
5. 结合知识库内容进行比对检查

检查维度：
- 低级错误：错别字、语法错误、格式不规范
- 隐含风险：金额异常、条款冲突、权利义务不对等
- 违禁词：用户配置的敏感词汇列表
- 表述问题：绝对化用语、模糊表述、法律风险措辞
- 合规性：是否符合招投标法规、合同法规等

输出格式要求：
- 每条问题标注严重程度（error/warning/info）
- 给出具体位置和原文
- 给出修改建议"""


# ─── 3. 体检台主协调员系统提示 ───
INSPECTION_COORDINATOR_SYSTEM_PROMPT = """你是句龙照胆系统的体检台主协调员。你的职责是：
1. 接收用户上传的工程文档内容
2. 协调法规分析师和合规检查员进行联合审查
3. 汇总审查结果，生成结构化体检报告
4. 报告需包含：风险等级、问题详情、修改建议、法规依据

输出格式（JSON）：
{
  "overall_risk": "low|medium|high|critical",
  "summary": "总体评价",
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "低级错误|隐含风险|违禁词|表述问题|合规性",
      "location": "问题位置",
      "original": "原文内容",
      "suggestion": "修改建议",
      "regulation_ref": "法规依据"
    }
  ]
}"""


# ─── 合同类专属提示词 ───

CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT = """你是一名工程合同法规分析师。你的职责是：
1. 只能根据用户当前启用的知识库内容匹配适用依据
2. 识别合同文档中可能存在的合规风险点
3. 列出相关条文和合规要求
4. 你只能分析法规，不能修改任何文档内容
5. 禁止引用未出现在知识库来源中的法规、法律、规范名称

合同审查维度：
- 权利义务对等性：合同双方权利义务是否对等
- 违约责任明确性：违约条款是否明确可执行
- 金额与付款条款：合同金额、付款方式、履约期限是否清晰
- 不可抗力条款：不可抗力条款是否完备
- 争议解决机制：争议解决方式是否合理
- 绝对化用语：是否存在"最优惠"、"最低价"等绝对化表述

输出格式要求：
- 列出发现的风险点
- 引用具体法规条款
- 给出合规建议"""


CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT = """你是一名工程合同合规检查员。你的职责是：
1. 检查合同文档中的低级错误（错别字、格式错误、逻辑矛盾）
2. 识别隐含的风险（金额异常、条款冲突、权利义务不对等）
3. 检查违禁词（用户配置的敏感词汇）
4. 检查表述不妥当的地方（绝对化用语、模糊表述、法律风险措辞）
5. 结合知识库内容进行比对检查

合同检查维度：
- 权利义务对等性：合同双方权利义务是否对等
- 违约责任明确性：违约条款是否明确可执行
- 金额与付款条款：合同金额、付款方式、履约期限是否清晰
- 不可抗力条款：不可抗力条款是否完备
- 争议解决机制：争议解决方式是否合理
- 绝对化用语：是否存在"最优惠"、"最低价"等绝对化表述

输出格式要求：
- 每条问题标注严重程度（error/warning/info）
- 给出具体位置和原文
- 给出修改建议"""


def get_prompts_for_scenario(scenario: str) -> dict[str, str]:
    """根据应用场景返回对应 prompt 模板。unknown/非法值兜底到 bidding。"""
    if scenario == "contract":
        return {
            "regulation": CONTRACT_REGULATION_ANALYST_SYSTEM_PROMPT,
            "inspection": CONTRACT_COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
        }
    return {
        "regulation": REGULATION_ANALYST_SYSTEM_PROMPT,
        "inspection": COMPLIANCE_INSPECTOR_SYSTEM_PROMPT,
    }


# ─── 4. 格式化函数 ───

def _safe_mask(text: str) -> str:
    try:
        return mask_sensitive_data(text).text
    except Exception:
        return text


def format_regulation_prompt(
    document_text: str,
    regulation_base: dict[str, Any] | None = None,
    max_length: int | None = None,
) -> str:
    """格式化法规分析请求"""
    max_length = max_length or _prompt_char_budget()
    masked_text = _safe_mask(document_text)
    return f"""请分析以下工程文档的法规合规性。

{format_regulation_base_context(regulation_base)}

文档内容：
{_truncate_text(masked_text, max_length)}

要求：只能引用上述知识库来源标题，禁止引用未配置的法律法规名称。"""


def format_regulation_base_context(regulation_base: dict[str, Any] | None) -> str:
    if not regulation_base:
        return "当前没有可用知识库来源。"
    sources = regulation_base.get("sources", [])
    snippets = regulation_base.get("snippets", [])
    source_lines = [f"- {source.get('title')}" for source in sources if source.get("title")]
    snippet_lines = [
        f"- [{snippet.get('title')}] {snippet.get('path_label')}: {snippet.get('content')}"
        for snippet in snippets
        if snippet.get("content")
    ]
    return "知识库来源（仅允许引用这些标题）：\n" + "\n".join(source_lines) + "\n\n知识库片段：\n" + "\n".join(snippet_lines)


def format_inspection_prompt(
    document_text: str,
    regulation_result: str,
    regulation_base: dict[str, Any] | None = None,
    taboo_words: list[str] | None = None,
    max_length: int | None = None,
) -> str:
    """格式化合规检查请求"""
    max_length = max_length or _prompt_char_budget()
    masked_text = _safe_mask(document_text)
    taboo_context = ""
    if taboo_words:
        taboo_context = f"\n\n用户配置的违禁词列表：{', '.join(taboo_words)}"

    regulation_context = format_regulation_base_context(regulation_base)
    fixed_context_len = len(regulation_context) + len(regulation_result) + len(taboo_context) + 700
    document_budget = max(MIN_DOCUMENT_CHARS, max_length - fixed_context_len)

    return f"""请对以下工程文档进行全面合规检查：

文档内容：
{_truncate_text(masked_text, document_budget)}

{regulation_context}

法规分析结果：
{regulation_result}
{taboo_context}

请检查：
1. 低级错误（错别字、格式、逻辑矛盾）
2. 隐含风险（金额异常、条款冲突）
3. 违禁词
4. 表述不妥当
5. 合规性

引用约束：所有 regulation_ref / citation / regulation_refs 只能使用上述“知识库来源”标题或“违禁词:<词>”，禁止输出未配置的法律名称。"""


def format_summary_prompt(
    regulation_result: str,
    inspection_result: str,
    allowed_refs: list[str],
    max_length: int | None = None,
) -> str:
    """格式化汇总报告请求"""
    max_length = max_length or _prompt_char_budget()
    refs_text = chr(10).join(f"- {ref}" for ref in allowed_refs) or "- 无"
    fixed_context_len = len(refs_text) + 500
    result_budget = max(1000, (max_length - fixed_context_len) // 2)
    return f"""请汇总以下审查结果，生成结构化体检报告：

法规分析：
{_truncate_text(regulation_result, result_budget)}

合规检查：
{_truncate_text(inspection_result, result_budget)}

允许引用来源：
{refs_text}

请输出 JSON 格式：
{{
  "overall_risk": "low|medium|high|critical",
  "summary": "总体评价",
  "issues": [...],
  "regulation_refs": [...]
}}

要求：regulation_refs 以及 issues 中的 regulation_ref/citation 只能从“允许引用来源”选择，禁止编造或补充其他法规名称。"""


def format_inspection_date() -> str:
    """返回当前体检日期"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
