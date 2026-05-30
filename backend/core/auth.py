from __future__ import annotations

from fastapi import HTTPException, Request

from core.config import settings

API_KEY_HEADER = "X-API-Key"


async def get_current_user(request: Request) -> dict:
    api_key = request.headers.get(API_KEY_HEADER)
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"user_id": "default", "api_key": api_key}
