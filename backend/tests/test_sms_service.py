"""SmsService 单元测试（使用真实 Redis）。

通过 monkeypatch 设置 sms_fixed_code，避免触发真实阿里云下发；
通过 monkeypatch 替换 get_redis 为独立测试连接，隔离键空间。
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import redis.asyncio as redis_async

from app.core.config import settings
from app.services import sms_service

_TEST_PHONE = "17387613231"
_FIXED_CODE = "123456"


class _CodeReadBarrierRedis:
    """让旧的 GET-然后-DEL 实现稳定暴露并发窗口。"""

    def __init__(self, redis, code_key: str):
        self._redis = redis
        self._code_key = code_key
        self._code_reads = 0
        self._both_read = asyncio.Event()

    def __getattr__(self, name):
        return getattr(self._redis, name)

    async def get(self, key):
        value = await self._redis.get(key)
        if key == self._code_key:
            self._code_reads += 1
            if self._code_reads == 2:
                self._both_read.set()
            await self._both_read.wait()
        return value


class _NoEvalRedis:
    pass


class _EvalFailureRedis:
    async def eval(self, *args, **kwargs):
        raise RuntimeError("redis unavailable")


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
    assert sms_service.validate_phone("+8617387613231") is False
    assert sms_service.validate_phone("１３８００１３８０００") is False
    assert sms_service.validate_phone("13800138000\n") is False
    assert sms_service.validate_phone("abc") is False
    assert sms_service.validate_phone("") is False


def test_sms_verification_keys_share_a_redis_hash_tag():
    phone = _TEST_PHONE
    expected_tag = f"{{{phone}}}"

    assert expected_tag in sms_service._code_key(phone)
    assert expected_tag in sms_service._verify_attempts_key(phone)
    assert expected_tag in sms_service._rate_key(phone)


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
    stored = await redis_conn.get(sms_service._code_key(_TEST_PHONE))
    rate = await redis_conn.get(sms_service._rate_key(_TEST_PHONE))
    assert stored == code
    assert rate == "1"
    ttl = await redis_conn.ttl(sms_service._code_key(_TEST_PHONE))
    assert 0 < ttl <= sms_service.CODE_TTL_SECONDS


@pytest.mark.asyncio
async def test_send_code_with_ip_records(redis_conn):
    await sms_service.send_code(_TEST_PHONE, ip="1.2.3.4")
    ip_count = await redis_conn.get("SMS:rate:ip:1.2.3.4")
    assert ip_count == "1"


@pytest.mark.asyncio
async def test_verify_code_success(redis_conn):
    await sms_service.send_code(_TEST_PHONE)
    await redis_conn.set(sms_service._verify_attempts_key(_TEST_PHONE), "1")
    assert await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE) is True
    assert await redis_conn.get(sms_service._verify_attempts_key(_TEST_PHONE)) is None
    # 验证码一次性：再次校验应失败
    assert await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE) is False


@pytest.mark.asyncio
async def test_verify_code_cannot_be_replayed_concurrently(redis_conn, monkeypatch):
    await sms_service.send_code(_TEST_PHONE)
    barrier_redis = _CodeReadBarrierRedis(redis_conn, sms_service._code_key(_TEST_PHONE))
    monkeypatch.setattr(sms_service, "get_redis", lambda: barrier_redis)

    results = await asyncio.gather(
        sms_service.verify_code(_TEST_PHONE, _FIXED_CODE),
        sms_service.verify_code(_TEST_PHONE, _FIXED_CODE),
    )

    assert sorted(results) == [False, True]


@pytest.mark.asyncio
async def test_verify_code_wrong():
    await sms_service.send_code(_TEST_PHONE)
    assert await sms_service.verify_code(_TEST_PHONE, "000000") is False


@pytest.mark.asyncio
async def test_verify_code_rejects_non_ascii_code_without_consuming_attempt(redis_conn):
    await sms_service.send_code(_TEST_PHONE)

    assert await sms_service.verify_code(_TEST_PHONE, "１２３４５６") is False
    assert await redis_conn.get(sms_service._code_key(_TEST_PHONE)) == _FIXED_CODE
    assert await redis_conn.get(sms_service._verify_attempts_key(_TEST_PHONE)) is None


@pytest.mark.asyncio
async def test_verify_code_requires_eval(monkeypatch):
    monkeypatch.setattr(sms_service, "get_redis", lambda: _NoEvalRedis())

    with pytest.raises(sms_service.SmsVerificationInfrastructureError):
        await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE)


@pytest.mark.asyncio
async def test_verify_code_eval_failure_is_a_controlled_infrastructure_error(monkeypatch):
    monkeypatch.setattr(sms_service, "get_redis", lambda: _EvalFailureRedis())

    with pytest.raises(sms_service.SmsVerificationInfrastructureError) as exc_info:
        await sms_service.verify_code(_TEST_PHONE, _FIXED_CODE)

    assert str(exc_info.value) == sms_service.SMS_SERVICE_UNAVAILABLE_MESSAGE
    assert "redis unavailable" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_verify_code_does_not_touch_redis_for_invalid_code(monkeypatch):
    redis = type("Redis", (), {"eval": AsyncMock()})()
    monkeypatch.setattr(sms_service, "get_redis", lambda: redis)

    assert await sms_service.verify_code(_TEST_PHONE, "12345a") is False
    redis.eval.assert_not_awaited()


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
