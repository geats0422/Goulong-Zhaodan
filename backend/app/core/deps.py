"""依赖注入类型定义"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session


@dataclass
class InspectionDeps:
    """体检台 Agent 运行依赖"""

    project_id: str = "default"
    user_id: str = "anonymous"
    document_name: str = "未命名文档"
    application_scenario: str = "contract"
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


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
