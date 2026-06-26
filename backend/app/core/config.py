"""配置管理 — 从环境变量读取，不硬编码密钥"""
from __future__ import annotations

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用配置 — 开发时通过系统环境变量注入"""

    # 模型 API 配置（兼容 OpenAI 格式，支持任意提供商）
    model_api_key: str = ""
    model_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"

    api_key: str = "goulong-dev-key"

    jwt_secret_key: str = "goulong-jwt-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    database_url: str = "postgresql+asyncpg://postgres:your-password@localhost:5432/goulong"

    redis_url: str = "redis://localhost:6379"

    pageindex_vendor_path: str = "vendor/pageindex"

    # CORS 跨域配置（逗号分隔）
    cors_origins: str = "http://localhost:5174,http://localhost:5173"

    # 应用行为
    log_level: str = "INFO"
    max_document_length: int = 8000  # 单次体检最大字符数
    inspection_prompt_char_budget: int = 60000  # 体检 Agent 单次提示词字符预算

    api_key_encryption_secret: str = "dev-encryption-secret-change-in-production"

    trusted_proxy_count: int = 0

    environment: str = "development"
    data_encryption_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",         # 本地开发时若存在 .env 则读取（不提交到 git）
        env_file_encoding="utf-8",
        extra="ignore",          # 忽略未知环境变量
    )


# 全局配置实例
settings = Settings()

_INSECURE_DEFAULTS = {
    "jwt_secret_key": "goulong-jwt-dev-secret-change-in-production",
    "api_key_encryption_secret": "dev-encryption-secret-change-in-production",
    "api_key": "goulong-dev-key",
}
if settings.environment != "production":
    for attr, default in _INSECURE_DEFAULTS.items():
        if getattr(settings, attr) == default:
            _logger.warning("开发环境使用默认 %s，请勿暴露此服务到公网", attr)


def get_model_name() -> str:
    """返回当前使用的 LLM 模型标识"""
    return settings.model_name


def get_model_config() -> dict[str, str]:
    """返回模型客户端配置字典"""
    return {
        "api_key": settings.model_api_key,
        "base_url": settings.model_base_url,
    }


def assert_production_security() -> None:
    if settings.environment != "production":
        return
    defaults = {
        "jwt_secret_key": "goulong-jwt-dev-secret-change-in-production",
        "api_key_encryption_secret": "dev-encryption-secret-change-in-production",
        "api_key": "goulong-dev-key",
    }
    for attr, default in defaults.items():
        if getattr(settings, attr) == default:
            raise RuntimeError(f"生产环境不允许使用默认 {attr}")
    if not settings.model_api_key:
        raise RuntimeError("生产环境必须配置 MODEL_API_KEY")
    if not settings.data_encryption_key:
        raise RuntimeError("生产环境必须配置 DATA_ENCRYPTION_KEY")
    if "your-password" in settings.database_url:
        raise RuntimeError("生产环境必须修改 DATABASE_URL 中的默认密码")
