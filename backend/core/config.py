"""配置管理 — 从环境变量读取，不硬编码密钥"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置 — 开发时通过系统环境变量注入"""

    # 模型 API 配置（兼容 OpenAI 格式，支持任意提供商）
    model_api_key: str = ""
    model_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"

    api_key: str = "goulong-dev-key"

    database_url: str = "sqlite+aiosqlite:///./data/goulong.db"

    pageindex_vendor_path: str = "vendor/pageindex"

    # 应用行为
    log_level: str = "INFO"
    max_document_length: int = 8000  # 单次体检最大字符数

    model_config = SettingsConfigDict(
        env_file=".env",         # 本地开发时若存在 .env 则读取（不提交到 git）
        env_file_encoding="utf-8",
        extra="ignore",          # 忽略未知环境变量
    )


# 全局配置实例
settings = Settings()


def get_model_name() -> str:
    """返回当前使用的 LLM 模型标识"""
    return settings.model_name


def get_model_config() -> dict[str, str]:
    """返回模型客户端配置字典"""
    return {
        "api_key": settings.model_api_key,
        "base_url": settings.model_base_url,
    }
