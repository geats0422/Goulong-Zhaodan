from __future__ import annotations

import datetime
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for mod_name in [
    "pageindex",
    "pydantic_ai",
    "pydantic_ai.agent",
    "pydantic_ai.models",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

if "markitdown" not in sys.modules or not hasattr(sys.modules.get("markitdown"), "MarkItDown"):
    _fake_md = types.ModuleType("markitdown")
    _fake_md.MarkItDown = MagicMock()
    sys.modules["markitdown"] = _fake_md

fake_inspector_module = types.ModuleType("app.agents.inspector")


async def _fake_run_inspection(*args, **kwargs):
    return {"overall_risk": "low", "summary": "", "issues": [], "regulation_refs": []}


fake_inspector_module.run_inspection = _fake_run_inspection
sys.modules["app.agents.inspector"] = fake_inspector_module

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import redis.asyncio as redis_async  # noqa: E402
from goulong_auth.models import User  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.auth import create_refresh_token, hash_password  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import async_session  # noqa: E402
from app.services import sms_service  # noqa: E402
from main import app  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402

VALID_PASSWORD = "TestPass123"
EMAIL_CODE = "123456"
PHONE_CODE = "123456"


async def _create_user(
    *,
    username: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    is_active: bool = True,
    stored_hash: str | None = None,
) -> tuple[object, datetime.datetime]:
    user = User(
        username=username,
        email=email,
        phone=phone,
        nickname=username or email or phone or "auth-user",
        hashed_password=stored_hash or hash_password(VALID_PASSWORD),
        is_active=is_active,
    )
    async with async_session() as db:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user.id, user.updated_at


async def _load_user(user_id: object) -> User:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one()


async def _set_user_active_by_email(email: str, is_active: bool) -> None:
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.is_active = is_active
        await db.commit()


async def _preset_code(key: str, code: str = EMAIL_CODE) -> None:
    """直接向 Redis 预置验证码，绕过发码端点的 60s 限频（用于验证码流程测试）。"""
    r = redis_async.from_url(settings.redis_url, decode_responses=True)
    await r.set(key, code, ex=300)
    await r.aclose()


@pytest_asyncio.fixture
async def client(monkeypatch):
    """注册/登录逻辑测试用客户端：mock 验证码校验为恒真，聚焦注册逻辑。

    注册请求需带 email_code/phone_code 字段（RegisterRequest 契约要求），
    但校验逻辑被替换，故 code 值任意。
    """
    from app.core.rate_limit import register_limiter, send_code_limiter
    from app.services import email_service, sms_service

    assert_safe_database_for_cleanup()
    register_limiter.reset()
    send_code_limiter.reset()

    async def _always_true(*args, **kwargs):
        return True

    monkeypatch.setattr(email_service, "verify_code", _always_true)
    monkeypatch.setattr(sms_service, "verify_code", _always_true)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def real_client(monkeypatch):
    """验证码流程测试用客户端：不 mock 校验，使用真实 Redis + fixed_code。"""
    from app.core import redis_client
    from app.core.rate_limit import register_limiter, send_code_limiter

    assert_safe_database_for_cleanup()
    register_limiter.reset()
    send_code_limiter.reset()
    monkeypatch.setattr(settings, "email_fixed_code", EMAIL_CODE)
    monkeypatch.setattr(settings, "sms_fixed_code", PHONE_CODE)

    # 重置全局 redis 单例：避免跨测试复用绑定到旧 event loop 的连接
    await redis_client.close_redis()

    # 清理验证码相关 redis keys，隔离测试（用临时连接）
    r = redis_async.from_url(settings.redis_url, decode_responses=True)
    for pat in ("EMAIL:*", "SMS:*"):
        keys = await r.keys(pat)
        if keys:
            await r.delete(*keys)
    await r.aclose()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    # 测试后关闭单例，避免泄漏到下一个测试的 event loop
    await redis_client.close_redis()


# ---------------------------------------------------------------------------
# 注册：密码校验 / 查重（验证码校验已 mock 为恒真）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "testuser1@example.com",
        "nickname": "testuser1",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["nickname"] == "testuser1"
    assert data["email"] == "t***1@example.com"
    assert "access_token" in data
    assert "refresh_token" not in data
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "dup@example.com",
        "nickname": "testuser_dup",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    resp = await client.post("/auth/register", json={
        "email": "dup@example.com",
        "nickname": "testuser_dup2",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_missing_identity(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "nickname": "noid_user",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_missing_code(client: AsyncClient):
    """有 email 但缺 email_code 应 422。"""
    resp = await client.post("/auth/register", json={
        "email": "nocode@example.com",
        "nickname": "nocode",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "shortpw@example.com",
        "nickname": "validname",
        "password": "Ab1",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_rejects_bcrypt_overlong_bytes(client: AsyncClient):
    overlong_password = "A" * 60 + "a" * 10 + "1!!"

    resp = await client.post("/auth/register", json={
        "email": "bcrypt-register-overlong@example.com",
        "nickname": "bcrypt-register-overlong",
        "password": overlong_password,
        "email_code": EMAIL_CODE,
    })

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_uppercase(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "noupc@example.com",
        "nickname": "validname2",
        "password": "testpass123",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_lowercase(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "nolow@example.com",
        "nickname": "validname3",
        "password": "TESTPASS123",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_digit(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "nodig@example.com",
        "nickname": "validname4",
        "password": "TestPassWord",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_has_space(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "spacepw@example.com",
        "nickname": "validname5",
        "password": "Test Pass123",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_weak(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "weakpw@example.com",
        "nickname": "validname6",
        "password": "Password123",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_allowed_special(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "specuser1@example.com",
        "nickname": "specuser1",
        "password": "TestPass123!",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_password_disallowed_special(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "specuser2@example.com",
        "nickname": "specuser2",
        "password": "TestPass123`",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_long(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "email": "longpw@example.com",
        "nickname": "longpw",
        "password": "A" * 129 + "a1",
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 密码登录 / refresh / me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identity_payload",
    [
        {"password": VALID_PASSWORD},
        {"email": "both-email@example.com", "phone": "13800000001", "password": VALID_PASSWORD},
        {"email": "email-username@example.com", "username": "email_username", "password": VALID_PASSWORD},
        {"phone": "13800000002", "username": "phone_username", "password": VALID_PASSWORD},
    ],
)
async def test_login_requires_exactly_one_identity(client: AsyncClient, identity_payload: dict[str, str]):
    resp = await client.post("/auth/login", json=identity_payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": VALID_PASSWORD},
        {"username": "a" * 51, "password": VALID_PASSWORD},
        {"username": "bad user", "password": VALID_PASSWORD},
        {"username": "bad$user", "password": VALID_PASSWORD},
        {"username": "1valid_user", "password": VALID_PASSWORD},
        {"username": "_valid_user", "password": VALID_PASSWORD},
        {"username": ".valid_user", "password": VALID_PASSWORD},
        {"username": "-valid_user", "password": VALID_PASSWORD},
        {"username": "valid_user", "password": ""},
        {"username": "valid_user", "password": "P" * 129},
    ],
)
async def test_login_rejects_invalid_username_or_password_bounds(
    client: AsyncClient,
    payload: dict[str, str],
):
    resp = await client.post("/auth/login", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_bad_hash_returns_generic_401(client: AsyncClient):
    await _create_user(email="bad-hash@example.com", stored_hash="not-a-bcrypt-hash")

    resp = await client.post("/auth/login", json={
        "email": "bad-hash@example.com",
        "password": VALID_PASSWORD,
    })

    assert resp.status_code == 401
    assert resp.json() == {"detail": "用户名/邮箱/手机号或密码错误"}


@pytest.mark.asyncio
async def test_login_bcrypt_overlong_password_returns_generic_401(client: AsyncClient):
    await _create_user(email="bcrypt-long-password@example.com")

    resp = await client.post("/auth/login", json={
        "email": "bcrypt-long-password@example.com",
        "password": "P" * 128,
    })

    assert resp.status_code == 401
    assert resp.json() == {"detail": "用户名/邮箱/手机号或密码错误"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identity_field", "identity_value"),
    [
        ("username", "password_username"),
        ("email", "password-email@example.com"),
        ("phone", "13800000003"),
    ],
)
async def test_password_login_updates_user_timestamp_and_binding(
    client: AsyncClient,
    identity_field: str,
    identity_value: str,
):
    user_id, before = await _create_user(**{identity_field: identity_value})
    login_value = f"  {identity_value.upper()}  " if identity_field == "username" else identity_value

    resp = await client.post(
        "/auth/login",
        json={identity_field: login_value, "password": VALID_PASSWORD},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["require_phone_binding"] is (identity_field != "phone")
    assert "refresh_token" not in data
    assert "refresh_token" in resp.cookies
    updated = await _load_user(user_id)
    assert updated.updated_at > before


@pytest.mark.asyncio
async def test_username_login_normalizes_lookup_and_throttle_key(client: AsyncClient, monkeypatch):
    await _create_user(username="normalized_user")
    from app.api.v1 import auth

    check = MagicMock(return_value=0)
    reset = MagicMock()
    monkeypatch.setattr(auth.login_throttle, "check", check)
    monkeypatch.setattr(auth.login_throttle, "reset", reset)

    resp = await client.post(
        "/auth/login",
        json={"username": "  NORMALIZED_USER  ", "password": VALID_PASSWORD},
    )

    assert resp.status_code == 200
    check.assert_called_once_with("normalized_user")
    reset.assert_called_once_with("normalized_user")


@pytest.mark.asyncio
async def test_username_and_password_errors_are_generic_401(client: AsyncClient):
    await _create_user(username="generic_user")

    wrong_password = await client.post(
        "/auth/login",
        json={"username": " GENERIC_USER ", "password": "WrongPass999"},
    )
    missing_username = await client.post(
        "/auth/login",
        json={"username": "missing_user", "password": VALID_PASSWORD},
    )

    assert wrong_password.status_code == 401
    assert missing_username.status_code == 401
    assert wrong_password.json()["detail"] == missing_username.json()["detail"]


@pytest.mark.asyncio
async def test_inactive_username_login_returns_403_without_tokens(client: AsyncClient):
    await _create_user(username="inactive_user", is_active=False)

    resp = await client.post(
        "/auth/login",
        json={"username": " INACTIVE_USER ", "password": VALID_PASSWORD},
    )

    assert resp.status_code == 403
    assert "access_token" not in resp.json()
    assert "refresh_token" not in resp.cookies


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "nickname": "loginuser",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    resp = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "loginuser"
    assert "access_token" in data
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "email": "wrongpw@example.com",
        "nickname": "wrongpass",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    resp = await client.post("/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "WrongPass999",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": VALID_PASSWORD,
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_success(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "email": "refresh@example.com",
        "nickname": "refreshuser",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    refresh_token = reg.cookies.get("refresh_token")
    client.cookies.set("refresh_token", refresh_token)

    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(client: AsyncClient):
    email = "refresh-inactive@example.com"
    reg = await client.post("/auth/register", json={
        "email": email,
        "nickname": "refresh-inactive",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    await _set_user_active_by_email(email, False)
    client.cookies.set("refresh_token", reg.cookies.get("refresh_token"))

    resp = await client.post("/auth/refresh")

    assert resp.status_code == 403
    assert resp.json() == {"detail": "账号已被停用"}
    assert "access_token" not in resp.json()


@pytest.mark.asyncio
async def test_refresh_rejects_missing_user(client: AsyncClient, monkeypatch):
    from app.api.v1 import auth

    refresh_token, _ = create_refresh_token(uuid.uuid4())
    monkeypatch.setattr(auth, "is_refresh_token_revoked", AsyncMock(return_value=False))
    client.cookies.set("refresh_token", refresh_token)

    resp = await client.post("/auth/refresh")

    assert resp.status_code == 401
    assert "access_token" not in resp.json()


@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient):
    client.cookies.set("refresh_token", "invalid.token.here")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client: AsyncClient):
    reg = await client.post("/auth/register", json={
        "email": "me@example.com",
        "nickname": "meuser",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    access_token = reg.json()["access_token"]

    resp = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {access_token}",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["nickname"] == "meuser"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 发送验证码端点（真实 Redis + fixed_code）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_code_success(real_client: AsyncClient):
    resp = await real_client.post("/auth/send-email-code", json={"email": "newcode@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"sent": True, "expires_in": 300}


@pytest.mark.asyncio
async def test_send_sms_code_success(real_client: AsyncClient):
    resp = await real_client.post("/auth/send-sms-code", json={"phone": "13800138000"})
    assert resp.status_code == 200
    assert resp.json()["sent"] is True


@pytest.mark.asyncio
async def test_send_email_code_invalid_address(real_client: AsyncClient):
    resp = await real_client.post("/auth/send-email-code", json={"email": "not-an-email"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_send_email_code_hides_provider_error(client: AsyncClient, monkeypatch):
    from app.services import email_service

    async def fail_send_code(*args, **kwargs):
        raise email_service.EmailSendError("aliyun raw error")

    monkeypatch.setattr(email_service, "send_verification_code", fail_send_code)

    resp = await client.post("/auth/send-email-code", json={"email": "provider-error@example.com"})

    assert resp.status_code == 502
    assert resp.json() == {"detail": email_service.EMAIL_SERVICE_UNAVAILABLE_MESSAGE}
    assert "aliyun raw error" not in resp.text


@pytest.mark.asyncio
async def test_send_sms_code_invalid_phone(real_client: AsyncClient):
    resp = await real_client.post("/auth/send-sms-code", json={"phone": "12345"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 注册验证码校验（真实 Redis）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_with_real_email_code(real_client: AsyncClient):
    email = "realcode@example.com"
    await _preset_code(f"EMAIL:code:{email}")
    resp = await real_client.post("/auth/register", json={
        "email": email,
        "nickname": "realcode",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_register_wrong_email_code(real_client: AsyncClient):
    email = "wrongcode@example.com"
    await _preset_code(f"EMAIL:code:{email}")
    resp = await real_client.post("/auth/register", json={
        "email": email,
        "nickname": "wrongcode",
        "password": VALID_PASSWORD,
        "email_code": "000000",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_with_real_phone_code(real_client: AsyncClient):
    phone = "13900139000"
    await _preset_code(sms_service._code_key(phone), PHONE_CODE)
    resp = await real_client.post("/auth/register", json={
        "phone": phone,
        "nickname": "phoneuser",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# 验证码登录（真实 Redis）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_by_email_code(real_client: AsyncClient):
    email = "logincode@example.com"
    # 注册
    await _preset_code(f"EMAIL:code:{email}")
    await real_client.post("/auth/register", json={
        "email": email,
        "nickname": "logincode",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    # 注册消费了验证码，重新预置后验证码登录
    await _preset_code(f"EMAIL:code:{email}")
    resp = await real_client.post("/auth/login/code", json={"email": email, "code": EMAIL_CODE})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["require_phone_binding"] is True
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_by_phone_code(real_client: AsyncClient):
    phone = "13700137000"
    await _preset_code(sms_service._code_key(phone), PHONE_CODE)
    await real_client.post("/auth/register", json={
        "phone": phone,
        "nickname": "phone login",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    await _preset_code(sms_service._code_key(phone), PHONE_CODE)
    resp = await real_client.post("/auth/login/code", json={"phone": phone, "code": PHONE_CODE})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["require_phone_binding"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("identity_field", "identity_value", "requires_phone_binding"),
    [
        ("email", "code-email-timestamp@example.com", True),
        ("phone", "13800000004", False),
    ],
)
async def test_login_by_code_updates_user_timestamp_and_binding(
    client: AsyncClient,
    identity_field: str,
    identity_value: str,
    requires_phone_binding: bool,
):
    user_id, before = await _create_user(**{identity_field: identity_value})

    resp = await client.post(
        "/auth/login/code",
        json={identity_field: identity_value, "code": EMAIL_CODE},
    )

    assert resp.status_code == 200
    assert resp.json()["require_phone_binding"] is requires_phone_binding
    updated = await _load_user(user_id)
    assert updated.updated_at > before


@pytest.mark.asyncio
async def test_login_by_code_nonexistent(real_client: AsyncClient):
    email = "nouser@example.com"
    await _preset_code(f"EMAIL:code:{email}")
    resp = await real_client.post("/auth/login/code", json={"email": email, "code": EMAIL_CODE})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_by_code_wrong_code(real_client: AsyncClient):
    email = "badcode@example.com"
    await _preset_code(f"EMAIL:code:{email}")
    await real_client.post("/auth/register", json={
        "email": email,
        "nickname": "badcode",
        "password": VALID_PASSWORD,
        "email_code": EMAIL_CODE,
    })
    # 不预置新码，用错误码登录
    resp = await real_client.post("/auth/login/code", json={"email": email, "code": "000000"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_by_code_missing_identity(real_client: AsyncClient):
    resp = await real_client.post("/auth/login/code", json={"code": EMAIL_CODE})
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"email": "both-identities@example.com", "phone": "13800000005", "code": EMAIL_CODE},
        {"email": "", "phone": "", "code": EMAIL_CODE},
    ],
)
async def test_login_by_code_requires_exactly_one_identity(client: AsyncClient, payload: dict[str, str]):
    resp = await client.post("/auth/login/code", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/auth/register",
            {
                "email": "ascii-code-register@example.com",
                "nickname": "ascii-code-register",
                "password": VALID_PASSWORD,
                "email_code": "１２３４５６",
            },
        ),
        ("/auth/login/code", {"email": "ascii-code-login@example.com", "code": "１２３４５６"}),
        (
            "/auth/reset-password",
            {"phone": "13800000006", "code": "１２３４５６", "new_password": "NewPass456"},
        ),
    ],
)
async def test_auth_code_fields_reject_non_ascii_digits(
    client: AsyncClient,
    path: str,
    payload: dict[str, str],
):
    resp = await client.post(path, json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_sms_code_hides_provider_error(client: AsyncClient, monkeypatch):
    async def fail_send_code(*args, **kwargs):
        raise sms_service.SmsSendError("aliyun raw error")

    monkeypatch.setattr(sms_service, "send_code", fail_send_code)

    resp = await client.post("/auth/send-sms-code", json={"phone": "13800000007"})

    assert resp.status_code == 502
    assert resp.json() == {"detail": sms_service.SMS_SERVICE_UNAVAILABLE_MESSAGE}
    assert "aliyun raw error" not in resp.text


@pytest.mark.asyncio
async def test_reset_password_cannot_take_over_unbound_phone_after_binding(client: AsyncClient):
    registration = await client.post(
        "/auth/register",
        json={
            "email": "reset-takeover@example.com",
            "nickname": "reset-takeover",
            "password": VALID_PASSWORD,
            "email_code": EMAIL_CODE,
        },
    )
    assert registration.status_code == 201
    auth_headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

    bind = await client.post(
        "/settings/phone",
        headers=auth_headers,
        json={"phone": "13800000008", "code": PHONE_CODE},
    )
    assert bind.status_code == 200

    reset = await client.post(
        "/auth/reset-password",
        json={"phone": "13900000008", "code": PHONE_CODE, "new_password": "NewPass456"},
    )

    assert reset.status_code == 404
    old_password_login = await client.post(
        "/auth/login",
        json={"email": "reset-takeover@example.com", "password": VALID_PASSWORD},
    )
    assert old_password_login.status_code == 200


# ---------------------------------------------------------------------------
# 忘记密码重置 /auth/reset-password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient):
    """手机号注册用户 → 重置密码 → 旧密码登录失败、新密码登录成功。"""
    phone = "13600136000"
    await client.post("/auth/register", json={
        "phone": phone,
        "nickname": "resetuser",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    new_password = "NewPass456"
    resp = await client.post("/auth/reset-password", json={
        "phone": phone,
        "code": PHONE_CODE,
        "new_password": new_password,
    })
    assert resp.status_code == 200
    assert resp.json() == {"message": "密码重置成功"}

    resp_old = await client.post("/auth/login", json={"phone": phone, "password": VALID_PASSWORD})
    assert resp_old.status_code == 401
    resp_new = await client.post("/auth/login", json={"phone": phone, "password": new_password})
    assert resp_new.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalidates_existing_access_token(client: AsyncClient):
    phone = "13600136001"
    registered = await client.post("/auth/register", json={
        "phone": phone,
        "nickname": "reset-token-user",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    old_access_token = registered.json()["access_token"]
    old_refresh_token = registered.cookies.get("refresh_token")

    resp = await client.post("/auth/reset-password", json={
        "phone": phone,
        "code": PHONE_CODE,
        "new_password": "NewPass456",
    })

    assert resp.status_code == 200
    new_login = await client.post("/auth/login", json={"phone": phone, "password": "NewPass456"})
    assert new_login.status_code == 200
    current_user = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert current_user.status_code == 401

    client.cookies.set("refresh_token", old_refresh_token)
    revoked_refresh = await client.post("/auth/refresh")
    assert revoked_refresh.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_rejects_bcrypt_overlong_new_password(client: AsyncClient):
    phone = "13600136002"
    await client.post("/auth/register", json={
        "phone": phone,
        "nickname": "reset-overlong",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })

    resp = await client.post("/auth/reset-password", json={
        "phone": phone,
        "code": PHONE_CODE,
        "new_password": "A" * 60 + "a" * 10 + "1!!",
    })

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_wrong_code(real_client: AsyncClient):
    """验证码错误 → 401（真实 Redis 校验）。"""
    phone = "13500135000"
    await _preset_code(sms_service._code_key(phone), PHONE_CODE)
    await real_client.post("/auth/register", json={
        "phone": phone,
        "nickname": "wrongreset",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    await _preset_code(sms_service._code_key(phone), PHONE_CODE)
    resp = await real_client.post("/auth/reset-password", json={
        "phone": phone,
        "code": "000000",
        "new_password": "NewPass456",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_nonexistent_phone(client: AsyncClient):
    """未注册手机号 → 404。"""
    resp = await client.post("/auth/reset-password", json={
        "phone": "13800000000",
        "code": PHONE_CODE,
        "new_password": "NewPass456",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_password_weak_password(client: AsyncClient):
    """新密码不符合强度 → 422。"""
    phone = "13400134000"
    await client.post("/auth/register", json={
        "phone": phone,
        "nickname": "weakreset",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    resp = await client.post("/auth/reset-password", json={
        "phone": phone,
        "code": PHONE_CODE,
        "new_password": "weak",
    })
    assert resp.status_code == 422
