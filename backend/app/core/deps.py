"""依赖注入类型定义"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.config import settings


@dataclass
class InspectionDeps:
    """体检台 Agent 运行依赖"""

    project_id: str = "default"
    user_id: str = "anonymous"
    application_scenario: str = "bidding"
    regulation_base: dict[str, Any] | None = None
    taboo_words: list[str] | None = None
    db: Any | None = None


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and settings.trusted_proxy_count > 0:
        parts = [p.strip() for p in forwarded.split(",")]
        idx = len(parts) - settings.trusted_proxy_count
        if idx >= 0:
            return parts[idx]
    if request.client:
        return request.client.host
    return "unknown"
