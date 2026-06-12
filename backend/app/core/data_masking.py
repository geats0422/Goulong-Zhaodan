from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MaskingResult:
    text: str
    mask_map: dict[str, str] = field(default_factory=dict)
    masked_count: int = 0


_MASKING_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\d+[\.,]\d{1,2}\s*(万|元|亿元|万元)"), "[金额]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号***]"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证***]"),
    (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "[银行卡***]"),
    (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "[邮箱***]"),
]


def mask_sensitive_data(text: str) -> MaskingResult:
    result_text = text
    total_count = 0
    for pattern, replacement in _MASKING_RULES:
        matches = pattern.findall(result_text)
        count = len(matches)
        result_text = pattern.sub(replacement, result_text)
        total_count += count
    return MaskingResult(text=result_text, mask_map={}, masked_count=total_count)
