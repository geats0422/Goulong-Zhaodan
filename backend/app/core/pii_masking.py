"""PII 脱敏工具 — API 响应中隐藏敏感字段"""
from __future__ import annotations

import re


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return phone
    prefix = digits[:3]
    suffix = digits[-4:]
    return f"{prefix}****{suffix}"
