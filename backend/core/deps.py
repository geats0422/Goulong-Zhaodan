"""依赖注入类型定义"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InspectionDeps:
    """体检台 Agent 运行依赖"""

    project_id: str = "default"
    user_id: str = "anonymous"
    regulation_base: dict[str, Any] | None = None  # 知识库内容
    taboo_words: list[str] | None = None  # 违禁词列表
    db: Any | None = None  # 数据库连接（预留）
