from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from goulong_auth.auth.jwt import decode_token as decode_shared_token

from app.api.v1.auth import router as auth_router
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.core.password_rules import validate_password
from app.core.database import get_db_session
from goulong_auth.config import auth_settings


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _signed_token(**overrides: object) -> str:
    now = datetime.datetime.now(datetime.UTC)
    payload: dict[str, object] = {
        "user_id": str(USER_ID),
        "product": "zhaodan",
        "exp": now + datetime.timedelta(hours=1),
        "iat": now,
    }
    payload.update(overrides)
    return jwt.encode(
        payload,
        auth_settings.JWT_SECRET_KEY,
        algorithm=auth_settings.JWT_ALGORITHM,
    )


def test_new_tokens_are_explicitly_typed_and_product_scoped() -> None:
    access_token = create_access_token(USER_ID)
    access = jwt.decode(
        access_token,
        auth_settings.JWT_SECRET_KEY,
        algorithms=[auth_settings.JWT_ALGORITHM],
    )
    refresh_token, refresh_jti = create_refresh_token(USER_ID)
    refresh = jwt.decode(
        refresh_token,
        auth_settings.JWT_SECRET_KEY,
        algorithms=[auth_settings.JWT_ALGORITHM],
    )

    assert access["typ"] == "access"
    assert access["product"] == "zhaodan"
    assert isinstance(access["iat"], int)
    assert isinstance(access["iat_ms"], int)
    assert decode_shared_token(access_token).iat == access["iat"]
    assert "jti" not in access
    assert refresh["typ"] == "refresh"
    assert refresh["product"] == "zhaodan"
    assert refresh["jti"] == refresh_jti


@pytest.mark.parametrize(
    ("token", "requested_type"),
    [
        (_signed_token(typ="refresh", jti="refresh-id"), "access"),
        (_signed_token(typ="access"), "refresh"),
        (_signed_token(typ="access", product="wenheng"), "access"),
    ],
)
def test_decode_token_rejects_wrong_type_or_product(token: str, requested_type: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, requested_type)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.parametrize(
    ("token", "requested_type", "accepted"),
    [
        (_signed_token(), "access", True),
        (_signed_token(jti="legacy-refresh-id"), "refresh", True),
        (_signed_token(), "refresh", False),
        (_signed_token(jti="legacy-refresh-id"), "access", False),
    ],
)
def test_legacy_token_compatibility_is_limited_by_jti(
    token: str,
    requested_type: str,
    accepted: bool,
) -> None:
    if accepted:
        assert decode_token(token, requested_type)["user_id"] == str(USER_ID)
        return

    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, requested_type)
    assert exc_info.value.status_code == 401


def test_legacy_access_token_without_iat_ms_is_shared_compatible() -> None:
    issued_at = int(datetime.datetime.now(datetime.UTC).timestamp())
    token = _signed_token(iat=issued_at)

    assert "iat_ms" not in jwt.decode(
        token,
        auth_settings.JWT_SECRET_KEY,
        algorithms=[auth_settings.JWT_ALGORITHM],
    )
    assert decode_shared_token(token).iat == issued_at
    assert decode_token(token, "access")["iat"] == issued_at


@pytest.mark.parametrize("malformed_user_id", ["not-a-uuid", "", None, 123])
def test_malformed_user_id_is_always_generic_401(malformed_user_id: object) -> None:
    token = _signed_token(typ="access", user_id=malformed_user_id)

    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, "access")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.parametrize("claim", ["exp", "iat", "user_id", "product"])
def test_decode_token_requires_all_security_claims(claim: str) -> None:
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "user_id": str(USER_ID),
        "product": "zhaodan",
        "typ": "access",
        "exp": now + datetime.timedelta(minutes=5),
        "iat": now,
    }
    payload.pop(claim)
    token = jwt.encode(payload, auth_settings.JWT_SECRET_KEY, algorithm=auth_settings.JWT_ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, "access")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.parametrize(
    "token",
    [
        _signed_token(exp=datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)),
        jwt.encode(
            {
                "user_id": str(USER_ID),
                "product": "zhaodan",
                "typ": "access",
                "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5),
                "iat": datetime.datetime.now(datetime.UTC),
            },
            "different-signing-key",
            algorithm=auth_settings.JWT_ALGORITHM,
        ),
    ],
)
def test_decode_token_keeps_expiration_and_signature_verification_enabled(token: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        decode_token(token, "access")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _UserSession:
    def __init__(self, user: object) -> None:
        self.user = user

    async def execute(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self.user)


def _request(token: str):
    from starlette.requests import Request

    return Request({
        "type": "http",
        "method": "GET",
        "path": "/protected",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    })


@pytest.mark.asyncio
@pytest.mark.parametrize("db_user", [None, SimpleNamespace(id=USER_ID, is_active=False)])
async def test_current_user_rejects_deleted_or_inactive_user(db_user: object) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_request(create_access_token(USER_ID)), _UserSession(db_user))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_current_user_returns_verified_active_user() -> None:
    user = SimpleNamespace(id=USER_ID, is_active=True)

    current = await get_current_user(_request(create_access_token(USER_ID)), _UserSession(user))

    assert current.user_id == USER_ID
    assert current.is_active is True


@pytest.mark.asyncio
async def test_current_user_rejects_access_token_issued_before_password_change() -> None:
    password_changed_at = datetime.datetime.now(datetime.UTC)
    user = SimpleNamespace(id=USER_ID, is_active=True, password_changed_at=password_changed_at)
    old_token = _signed_token(iat=int(password_changed_at.timestamp()) - 1)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_request(old_token), _UserSession(user))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_current_user_rejects_access_token_issued_before_password_change_within_same_second() -> None:
    password_changed_at = datetime.datetime.now(datetime.UTC).replace(microsecond=200_000)
    user = SimpleNamespace(id=USER_ID, is_active=True, password_changed_at=password_changed_at)
    old_token = _signed_token(iat=int(password_changed_at.timestamp()))

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(_request(old_token), _UserSession(user))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_current_user_accepts_new_access_token_created_in_same_second_as_password_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.core.auth as auth_module

    password_changed_at = datetime.datetime.now(datetime.UTC).replace(microsecond=200_000)
    token_issued_at = password_changed_at.replace(microsecond=900_000)

    class _FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:
            return token_issued_at

    monkeypatch.setattr(auth_module, "datetime", SimpleNamespace(datetime=_FrozenDateTime))
    token = create_access_token(USER_ID)
    user = SimpleNamespace(id=USER_ID, is_active=True, password_changed_at=password_changed_at)
    token_payload = jwt.decode(
        token,
        auth_settings.JWT_SECRET_KEY,
        algorithms=[auth_settings.JWT_ALGORITHM],
    )

    current = await get_current_user(_request(token), _UserSession(user))

    assert current.user_id == USER_ID
    assert token_payload["iat"] == int(token_issued_at.timestamp())
    assert token_payload["iat_ms"] == int(token_issued_at.timestamp() * 1000)


def test_password_validation_uses_bcrypt_byte_limit() -> None:
    exact_limit = "A" * 60 + "a" * 10 + "1!"
    ascii_over_limit = exact_limit + "!"
    multibyte_over_limit = "Aa1" + "中" * 24

    assert len(exact_limit.encode("utf-8")) == 72
    assert validate_password(exact_limit) == []
    assert "72 字节" in ";".join(validate_password(ascii_over_limit))
    assert "72 字节" in "；".join(validate_password(multibyte_over_limit))


@pytest.mark.asyncio
async def test_access_token_cannot_call_refresh_endpoint() -> None:
    app = FastAPI()
    app.include_router(auth_router)

    async def session():
        yield _UserSession(None)

    app.dependency_overrides[get_db_session] = session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("refresh_token", create_access_token(USER_ID))
        response = await client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


@pytest.mark.asyncio
async def test_refresh_token_cannot_call_other_current_user_endpoint() -> None:
    app = FastAPI()
    app.include_router(auth_router)

    async def session():
        yield _UserSession(None)

    app.dependency_overrides[get_db_session] = session
    refresh_token, _ = create_refresh_token(USER_ID)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}
