"""EmailService 单元测试（使用真实 Redis）。

通过 monkeypatch 设置 email_fixed_code，避免触发真实阿里云 DirectMail 下发；
通过 monkeypatch 替换 get_redis 为独立测试连接，隔离键空间。
模板渲染与通知类函数（未配置时返回 None）单独覆盖。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import redis.asyncio as redis_async

from app.core.config import settings
from app.services import email_service

_TEST_EMAIL = "test@example.com"
_FIXED_CODE = "123456"


class _BrokenRedis:
    async def exists(self, _key):
        raise RuntimeError("redis password leaked")


@pytest_asyncio.fixture
async def redis_conn():
    """每个测试创建独立的 Redis 连接（避免 event loop 冲突）。"""
    conn = redis_async.from_url(settings.redis_url, decode_responses=True)
    yield conn
    await conn.aclose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_redis(redis_conn):
    """每个测试前后清理 EMAIL:* keys。"""
    keys = await redis_conn.keys("EMAIL:*")
    if keys:
        await redis_conn.delete(*keys)
    yield
    keys = await redis_conn.keys("EMAIL:*")
    if keys:
        await redis_conn.delete(*keys)


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(monkeypatch, redis_conn):
    """替换 email_service 中的 get_redis 调用为测试连接。"""
    monkeypatch.setattr(email_service, "get_redis", lambda: redis_conn)
    monkeypatch.setattr(settings, "email_fixed_code", _FIXED_CODE)


def test_generate_code_length_6():
    code = email_service.generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_validate_email_valid():
    assert email_service.validate_email("user@example.com") is True
    assert email_service.validate_email("a.b+tag@sub.domain.co") is True


def test_validate_email_invalid():
    assert email_service.validate_email("plainaddress") is False
    assert email_service.validate_email("missing@dot") is False
    assert email_service.validate_email("@nodomain.com") is False
    assert email_service.validate_email("") is False


def test_wrap_email_contains_brand_and_design():
    html = email_service._wrap_email("标题", "<p>正文</p>")
    # 品牌与内容
    assert "句龙 · 照胆" in html
    assert "标题" in html
    assert "<p>正文</p>" in html
    # DESIGN.md（Neo-Chinese Cyberpunk）：黑曜石底 + 鎏金主色
    assert "#0A0A0A" in html
    assert "#D4AF37" in html
    # DESIGN.md：Syne 标题字体 + JetBrains Mono 系统标签
    assert "Syne" in html
    assert "JetBrains Mono" in html
    # DESIGN.md：Golden Thread 渐隐金线分隔
    assert "linear-gradient" in html


def test_render_auth_code_template():
    body = email_service._render("auth_code.html", code=_FIXED_CODE)
    assert _FIXED_CODE in body


@pytest.mark.asyncio
async def test_send_verification_code_success():
    code, expires = await email_service.send_verification_code(_TEST_EMAIL)
    assert code == _FIXED_CODE
    assert expires == email_service.CODE_TTL_SECONDS


@pytest.mark.asyncio
async def test_send_verification_code_invalid_email():
    with pytest.raises(email_service.EmailInvalidAddressError):
        await email_service.send_verification_code("not-an-email")


@pytest.mark.asyncio
async def test_send_verification_code_hides_infrastructure_error(monkeypatch):
    monkeypatch.setattr(email_service, "get_redis", lambda: _BrokenRedis())

    with pytest.raises(email_service.EmailSendError) as exc_info:
        await email_service.send_verification_code(_TEST_EMAIL)

    assert str(exc_info.value) == email_service.EMAIL_SERVICE_UNAVAILABLE_MESSAGE
    assert "redis password leaked" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_verification_code_rate_limit():
    await email_service.send_verification_code(_TEST_EMAIL)
    with pytest.raises(email_service.EmailRateLimitError):
        await email_service.send_verification_code(_TEST_EMAIL)


@pytest.mark.asyncio
async def test_send_verification_code_redis_storage(redis_conn):
    code, _ = await email_service.send_verification_code(_TEST_EMAIL)
    stored = await redis_conn.get(f"EMAIL:code:{_TEST_EMAIL}")
    rate = await redis_conn.get(f"EMAIL:rate:{_TEST_EMAIL}")
    assert stored == code
    assert rate == "1"
    ttl = await redis_conn.ttl(f"EMAIL:code:{_TEST_EMAIL}")
    assert 0 < ttl <= email_service.CODE_TTL_SECONDS


@pytest.mark.asyncio
async def test_send_verification_code_with_ip_records(redis_conn):
    await email_service.send_verification_code(_TEST_EMAIL, ip="1.2.3.4")
    ip_count = await redis_conn.get("EMAIL:rate:ip:1.2.3.4")
    assert ip_count == "1"


@pytest.mark.asyncio
async def test_verify_code_success():
    await email_service.send_verification_code(_TEST_EMAIL)
    assert await email_service.verify_code(_TEST_EMAIL, _FIXED_CODE) is True
    # 验证码一次性：再次校验应失败
    assert await email_service.verify_code(_TEST_EMAIL, _FIXED_CODE) is False


@pytest.mark.asyncio
async def test_verify_code_wrong():
    await email_service.send_verification_code(_TEST_EMAIL)
    assert await email_service.verify_code(_TEST_EMAIL, "000000") is False


@pytest.mark.asyncio
async def test_verify_code_expired_or_missing():
    assert await email_service.verify_code(_TEST_EMAIL, _FIXED_CODE) is False


@pytest.mark.asyncio
async def test_verify_code_lockout_after_max_attempts():
    await email_service.send_verification_code(_TEST_EMAIL)
    wrong = "000000"
    for _ in range(email_service.VERIFY_MAX_ATTEMPTS):
        assert await email_service.verify_code(_TEST_EMAIL, wrong) is False
    # 达到上限后即使提供正确验证码也失败
    assert await email_service.verify_code(_TEST_EMAIL, _FIXED_CODE) is False


@pytest.mark.asyncio
async def test_notification_functions_skip_when_not_configured(monkeypatch):
    """未配置 aliyun_dm_account_name 时，通知类函数应跳过并返回 None。"""
    monkeypatch.setattr(settings, "aliyun_dm_account_name", "")
    assert await email_service.send_payment_notification(
        "a@b.com", "用户", "照胆", "年", "99", "2026-12-31"
    ) is None
    assert await email_service.send_expire_reminder("a@b.com", "用户", "照胆", "2026-12-31", 7) is None
    assert await email_service.send_notification("a@b.com", "通知", "内容") is None
