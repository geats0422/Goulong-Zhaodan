"""SmsService 单元测试（使用真实 Redis）。

通过 monkeypatch 设置 sms_fixed_code，避免触发真实阿里云下发；
通过 monkeypatch 替换 get_redis 为独立测试连接，隔离键空间。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import redis.asyncio as redis_async

from app.core.config import settings
from app.services import sms_service

_TEST_PHONE = "17387613231"
_FIXED_CODE = "123456"


@pytest_asyncio.fixture
async def redis_conn():
    """每个测试创建独立的 Redis 连接（避免 event loop 冲突）。"""
    conn = redis_async.from_url(settings.redis_url, decode_responses=True)
    yield conn
    await conn.aclose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_redis(redis_conn):
    """每个测试前后清理 SMS:* keys。"""
    keys = await redis_conn.keys("SMS:*")
    if keys:
        await redis_conn.delete(*keys)
    yield
    keys = await redis_conn.keys("SMS:*")
    if keys:
        await redis_conn.delete(*keys)


@pytest_asyncio.fixture(autouse=True)
async def _patch_redis(monkeypatch, redis_conn):
    """替换 sms_service 中的 get_redis 调用为测试连接。"""
    monkeypatch.setattr(sms_service, "get_redis", lambda: redis_conn)
    monkeypatch.setattr(settings, "sms_fixed_code", _FIXED_CODE)


def test_generate_code_length_6():
    code = sms_service.generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_validate_phone_valid():
    assert sms_service.validate_phone("17387613231") is True
    assert sms_service.validate_phone("13800138000") is True


def test_validate_phone_invalid():
    assert sms_service.validate_phone("12345") is False
    assert sms_service.validate_phone("1738761323") is False
    assert sms_service.validate_phone("173876132311") is False
    assert sms_service.validate_phone("27387613231") is False
    assert sms_service.validate_phone("abc") is False
    assert sms_service.validate_phone("") is False


@pytest.mark.asyncio
async def test_send_code_success():
    code, expires = await sms_service.send_code(_TEST_PHONE)
    assert code == _FIXED_CODE
    assert expires == sms_service.CODE_TTL_SECONDS


@pytest.mark.asyncio
async def test_send_code_invalid_phone():
    with pytest.raises(sms_service.SmsInvalidPhoneError):
        await sms_service.send_code("12345")


@pytest.mark.asyncio
async def test_send_code_rate_limit():
    await sms_service.send_code(_TEST_PHONE)
    with pytest.raises(sms_service.SmsRateLimitError):
        await sms_service.send_code(_TEST_PHONE)


@pytest.mark.asyncio
async def test_send_code_redis_storage(redis_conn):
    code, _ = await sms_service.send_code(_TEST_PHONE)
    stored = await redis_conn.get(f"SMS:code:{_TEST_PHONE}")
    rate = await redis_conn.get(f"SMS:rate:{_TEST_PHONE}")
    assert stored == code
    assert rate == "1"
    ttl = await redis_conn.ttl(f"SMS:code:{_TEST_PHONE}")
    assert 0 < ttl <= sms_service.CODE_TTL_SECONDS


@pytest.mark.asyncio
async def test_send_code_with_ip_records(redis_conn):
    await sms_service.send_code(_TEST_PHONE, ip="1.2.3.4")
    ip_count = await redis_conn.get("SMS:rate:ip:1.2.3.4")
    assert ip_count == "1"


@pytest.mark.asyncio
async def test_verify_code_success():
    await sms_service.send_code(_TEST_PHONE)
    assert await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE) is True
    # 验证码一次性：再次校验应失败
    assert await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE) is False


@pytest.mark.asyncio
async def test_verify_code_wrong():
    await sms_service.send_code(_TEST_PHONE)
    assert await sms_service.verify_code(_TEST_PHONE, "000000") is False


@pytest.mark.asyncio
async def test_verify_code_expired_or_missing():
    assert await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE) is False


@pytest.mark.asyncio
async def test_verify_code_lockout_after_max_attempts(redis_conn):
    await sms_service.send_code(_TEST_PHONE)
    wrong = "000000"
    for _ in range(sms_service.VERIFY_MAX_ATTEMPTS):
        assert await sms_service.verify_code(_TEST_PHONE, wrong) is False
    # 达到上限后即使提供正确验证码也失败
    assert await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE) is False
