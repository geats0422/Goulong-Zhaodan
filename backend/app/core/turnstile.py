"""Cloudflare Turnstile 人机验证。

开发模式（turnstile_secret_key 为空）：跳过验证，方便本地调试。
生产模式（turnstile_secret_key 有值）：调用 Cloudflare siteverify API 验证 token。
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileError(Exception):
    """人机验证失败"""


async def verify_token(token: str, remote_ip: str | None = None) -> None:
    """验证 Turnstile token。失败抛 TurnstileError。

    开发模式（secret_key 为空）直接放行。
    """
    if not settings.turnstile_secret_key:
        logger.warning("turnstile_secret_key 未配置，跳过人机验证（仅开发环境）")
        return
    if not token:
        raise TurnstileError("人机验证未完成")
    data: dict[str, str] = {
        "secret": settings.turnstile_secret_key,
        "response": token,
    }
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_VERIFY_URL, data=data)
            result = resp.json()
    except Exception as e:
        logger.error("Turnstile siteverify 请求失败: %s", e)
        raise TurnstileError("人机验证服务暂时不可用") from e
    if not result.get("success"):
        codes = result.get("error-codes", [])
        logger.warning("Turnstile 验证失败: %s", codes)
        raise TurnstileError("人机验证失败")
