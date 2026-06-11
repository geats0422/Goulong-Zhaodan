from __future__ import annotations

import datetime

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from services.api_key_service import lookup_api_key_by_token


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


async def get_api_key_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_api_key")

    token = auth_header[7:]
    api_key = await lookup_api_key_by_token(db, token)
    if api_key is None:
        raise HTTPException(status_code=401, detail="invalid_api_key")

    if api_key.status == "revoked":
        raise HTTPException(status_code=401, detail="api_key_revoked")

    if api_key.expires_at is not None and api_key.expires_at < _utcnow():
        raise HTTPException(status_code=401, detail="api_key_expired")

    api_key.last_used_at = _utcnow()
    await db.commit()

    return {
        "user_id": api_key.user_id,
        "api_key_id": api_key.id,
        "scopes": api_key.scopes,
    }


def require_api_scope(required_scope: str):
    async def _check_scope(user: dict = Depends(get_api_key_user)) -> dict:
        if required_scope not in user["scopes"]:
            raise HTTPException(status_code=403, detail="insufficient_scope")
        return user

    return _check_scope
