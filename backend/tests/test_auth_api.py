from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

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
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from main import app  # noqa: E402
from tests.conftest import assert_safe_database_for_cleanup  # noqa: E402


VALID_PASSWORD = "TestPass123"
EMAIL_CODE = "123456"
PHONE_CODE = "123456"


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
    await _preset_code(f"SMS:code:{phone}", PHONE_CODE)
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
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_by_phone_code(real_client: AsyncClient):
    phone = "13700137000"
    await _preset_code(f"SMS:code:{phone}", PHONE_CODE)
    await real_client.post("/auth/register", json={
        "phone": phone,
        "nickname": "phone login",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    await _preset_code(f"SMS:code:{phone}", PHONE_CODE)
    resp = await real_client.post("/auth/login/code", json={"phone": phone, "code": PHONE_CODE})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


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
async def test_reset_password_wrong_code(real_client: AsyncClient):
    """验证码错误 → 401（真实 Redis 校验）。"""
    phone = "13500135000"
    await _preset_code(f"SMS:code:{phone}", PHONE_CODE)
    await real_client.post("/auth/register", json={
        "phone": phone,
        "nickname": "wrongreset",
        "password": VALID_PASSWORD,
        "phone_code": PHONE_CODE,
    })
    await _preset_code(f"SMS:code:{phone}", PHONE_CODE)
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
