"""手机号 + 短信验证码服务。

- 开发模式（sms_fixed_code 有值）：返回固定验证码，不真实下发短信。
- 生产模式（sms_fixed_code 为空 + aliyun_access_key_id 有值）：调用阿里云 Dysmsapi 真实下发。

限频策略：
- 同一手机号 60 秒内仅允许一次；
- 同一 IP 1 小时内最多 IP_RATE_LIMIT 次；
- 同一手机号验证错误 5 次后锁定 5 分钟。
"""
from __future__ import annotations

import json
import logging
import re
import secrets

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

CODE_TTL_SECONDS = 300
RATE_LIMIT_SECONDS = 60
IP_RATE_LIMIT = 10
IP_RATE_WINDOW = 3600
VERIFY_MAX_ATTEMPTS = 5
VERIFY_LOCKOUT_SECONDS = 300

PHONE_PATTERN = re.compile(r"^1[3-9][0-9]{9}$")
CODE_PATTERN = re.compile(r"^[0-9]{6}$")

SMS_SERVICE_UNAVAILABLE_MESSAGE = "短信服务暂不可用，请稍后再试"

_VERIFY_CODE_SCRIPT = """
local attempts = redis.call("GET", KEYS[2])
if attempts and tonumber(attempts) >= tonumber(ARGV[2]) then
    redis.call("DEL", KEYS[1])
    return 0
end

local stored = redis.call("GET", KEYS[1])
if stored and stored == ARGV[1] then
    redis.call("DEL", KEYS[1], KEYS[2])
    return 1
end

redis.call("INCR", KEYS[2])
redis.call("EXPIRE", KEYS[2], tonumber(ARGV[3]))
return 0
"""

# 短信场景 → 阿里云模板 CODE（照胆当前仅配置 login 模板，所有场景复用）
DEFAULT_SCENE = "login"
SCENE_TEMPLATES: dict[str, str] = {
    "login": settings.aliyun_sms_template_login,
    "register": settings.aliyun_sms_template_register,
    "forgot_password": settings.aliyun_sms_template_forgot_password,
}


class SmsRateLimitError(Exception):
    """60 秒内重复请求验证码"""


class SmsInvalidPhoneError(Exception):
    """手机号格式错误"""


class SmsSendError(Exception):
    """阿里云短信下发失败"""

    def __init__(self, *_args: object) -> None:
        super().__init__(SMS_SERVICE_UNAVAILABLE_MESSAGE)


class SmsVerificationInfrastructureError(Exception):
    """短信验证码校验依赖不可用。"""

    def __init__(self, *_args: object) -> None:
        super().__init__(SMS_SERVICE_UNAVAILABLE_MESSAGE)


def validate_phone(phone: str) -> bool:
    """校验中国大陆手机号格式"""
    return bool(phone and PHONE_PATTERN.fullmatch(phone))


def generate_code() -> str:
    """生成 6 位数字验证码"""
    return "".join(secrets.choice("0123456789") for _ in range(6))


def _rate_key(phone: str) -> str:
    return f"SMS:{{{phone}}}:rate"


def _code_key(phone: str) -> str:
    return f"SMS:{{{phone}}}:code"


def _verify_attempts_key(phone: str) -> str:
    return f"SMS:{{{phone}}}:verify"


def _ip_rate_key(ip: str) -> str:
    return f"SMS:rate:ip:{ip}"


async def check_rate_limit(phone: str) -> bool:
    """检查是否在 60 秒限频窗口内。True = 可发送，False = 已限频。"""
    redis = get_redis()
    return not await redis.exists(_rate_key(phone))


async def check_ip_rate_limit(ip: str) -> bool:
    """检查 IP 是否在 1 小时内发送超过限制。True = 可发送，False = 已限频。"""
    try:
        redis = get_redis()
        count = await redis.get(_ip_rate_key(ip))
        return not (count and int(count) >= IP_RATE_LIMIT)
    except Exception:
        logger.warning("Redis unavailable, SMS IP rate limit skipped")
        return True


async def record_ip_send(ip: str) -> None:
    """记录 IP 发送次数"""
    try:
        redis = get_redis()
        await redis.incr(_ip_rate_key(ip))
        await redis.expire(_ip_rate_key(ip), IP_RATE_WINDOW)
    except Exception:
        logger.warning("Redis unavailable, SMS IP rate record skipped")


_aliyun_client: object | None = None


def _get_aliyun_client() -> object:
    """懒加载并复用阿里云 Dysmsapi Client（线程安全，模块级单例）。"""
    global _aliyun_client
    if _aliyun_client is not None:
        return _aliyun_client

    from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
    from alibabacloud_tea_openapi import models as open_api_models

    if not settings.aliyun_access_key_id or not settings.aliyun_access_key_secret:
        raise SmsSendError

    config = open_api_models.Config(
        access_key_id=settings.aliyun_access_key_id,
        access_key_secret=settings.aliyun_access_key_secret,
        endpoint=settings.aliyun_sms_endpoint,
    )
    _aliyun_client = DysmsapiClient(config)
    return _aliyun_client


async def _send_via_aliyun(phone: str, code: str, scene: str) -> None:
    """调用阿里云 Dysmsapi 真实下发验证码。失败抛 SmsSendError。"""
    from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
    from alibabacloud_tea_util import models as util_models

    template_code = SCENE_TEMPLATES.get(scene, SCENE_TEMPLATES[DEFAULT_SCENE])
    if not template_code:
        raise SmsSendError

    request = dysmsapi_models.SendSmsRequest(
        phone_numbers=phone,
        sign_name=settings.aliyun_sms_sign_name,
        template_code=template_code,
        template_param=json.dumps({"code": code}),
    )
    try:
        client = _get_aliyun_client()
        resp = await client.send_sms_with_options_async(request, util_models.RuntimeOptions())  # type: ignore[attr-defined]
        body = resp.body
        if body is None or body.code != "OK":
            logger.error(
                "阿里云短信下发失败 phone=***%s provider_code=%s",
                phone[-4:],
                getattr(body, "code", None),
            )
            raise SmsSendError
        logger.info("阿里云短信下发成功 phone=***%s biz_id=%s", phone[-4:], getattr(body, "biz_id", ""))
    except SmsSendError:
        raise
    except Exception as e:
        logger.error("阿里云短信调用异常 phone=***%s", phone[-4:])
        raise SmsSendError from e


async def send_code(phone: str, ip: str | None = None, scene: str = DEFAULT_SCENE) -> tuple[str, int]:
    """生成并存储验证码。

    Returns:
        (code, expires_in_seconds)

    Raises:
        SmsInvalidPhoneError: 手机号格式错误
        SmsRateLimitError: 60 秒内重复请求 / IP 超限
    """
    if not validate_phone(phone):
        raise SmsInvalidPhoneError(f"手机号格式错误: {phone}")

    if ip and not await check_ip_rate_limit(ip):
        raise SmsRateLimitError("该 IP 发送次数过多，请稍后再试")

    redis = get_redis()

    if not await check_rate_limit(phone):
        raise SmsRateLimitError(f"60 秒内重复请求: {phone[-4:]}")

    code = settings.sms_fixed_code or generate_code()
    if settings.sms_fixed_code:
        logger.warning("sms_fixed_code is set — using fixed verification code (development only)")
    else:
        await _send_via_aliyun(phone, code, scene)

    await redis.set(_code_key(phone), code, ex=CODE_TTL_SECONDS)
    await redis.set(_rate_key(phone), "1", ex=RATE_LIMIT_SECONDS)

    if ip:
        await record_ip_send(ip)

    logger.info("SMS code sent: phone=***%s expires_in=%ss", phone[-4:], CODE_TTL_SECONDS)
    return code, CODE_TTL_SECONDS


async def _verify_code_atomically(redis: object, code_key: str, attempts_key: str, code: str) -> bool:
    eval_command = getattr(redis, "eval", None)
    if not callable(eval_command):
        raise SmsVerificationInfrastructureError

    try:
        result = await eval_command(
            _VERIFY_CODE_SCRIPT,
            2,
            code_key,
            attempts_key,
            code,
            VERIFY_MAX_ATTEMPTS,
            VERIFY_LOCKOUT_SECONDS,
        )
        return int(result) == 1
    except Exception as exc:
        logger.error("短信验证码原子校验失败")
        raise SmsVerificationInfrastructureError from exc


async def verify_code(phone: str, code: str) -> bool:
    """校验验证码。正确则删除（一次性）。失败 5 次后锁定该手机号验证码。"""
    if not validate_phone(phone):
        return False
    if not isinstance(code, str) or CODE_PATTERN.fullmatch(code) is None:
        return False

    redis = get_redis()
    return await _verify_code_atomically(
        redis,
        _code_key(phone),
        _verify_attempts_key(phone),
        code,
    )
