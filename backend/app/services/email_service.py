"""邮件推送服务。

- 开发模式（email_fixed_code 有值）：返回固定验证码，不真实下发邮件。
- 生产模式（email_fixed_code 为空 + aliyun_dm_account_name 有值）：调用阿里云 DirectMail 真实下发。

邮件正文使用本地 HTML 模板渲染，通过 SingleSendMail 接口发送。
config 中的 aliyun_dm_template_*（控制台触达邮件模板 ID）预留给后续批量触达场景，本服务不直接引用。
"""
from __future__ import annotations

import hmac
import logging
import re
import secrets
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "email_templates"
_template_cache: dict[str, str] = {}


def _load_template(filename: str) -> str:
    """读取本地邮件模板（带模块级缓存）。"""
    if filename not in _template_cache:
        _template_cache[filename] = (_TEMPLATE_DIR / filename).read_text(encoding="utf-8")
    return _template_cache[filename]


def _render(template_name: str, **kwargs: Any) -> str:
    """用 {var} 占位符渲染模板正文片段。"""
    return _load_template(template_name).format(**kwargs)


def _wrap_email(title: str, body_html: str, ref_code: str = "REF.GL-000") -> str:
    """统一邮件外壳：Neo-Chinese Cyberpunk 风格（参照 DESIGN.md）。

    黑曜石底（#0A0A0A）+ 深炭卡片（#121212）+ 鎏金描边（ghost border）
    + Syne 标题 + Golden Thread 分隔 + JetBrains Mono 系统标签。
    深度通过亮度分层与 ghost border 表达，不使用写实阴影；金色元素带 12px 发光。
    采用 table 布局以提升邮件客户端兼容性。
    """
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:0;background-color:#0A0A0A;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0A0A0A;">'
        '<tr><td align="center" style="padding:40px 16px;">'
        # 深炭卡片 + 鎏金 ghost border，0 圆角（monolithic）
        '<table role="presentation" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;'
        'background-color:#121212;border:1px solid rgba(212,175,55,0.25);">'
        # 顶部鎏金条：品牌标识 + 坐标标签
        '<tr><td style="border-bottom:1px solid rgba(212,175,55,0.25);padding:16px 24px;background-color:#0A0A0A;">'
        '<span style="font-family:\'JetBrains Mono\',\'Courier New\',monospace;font-size:11px;'
        'color:#D4AF37;letter-spacing:0.2em;">句龙 · 照胆</span>'
        '<span style="float:right;font-family:\'JetBrains Mono\',\'Courier New\',monospace;'
        'font-size:10px;color:#99907C;letter-spacing:0.1em;">'
        f"{ref_code}</span>"
        "</td></tr>"
        # 标题：Syne + 紧字距 + 鎏金发光（text-shadow 渐进增强）
        '<tr><td style="padding:28px 24px 0;">'
        '<h2 style="font-family:\'Syne\',\'Arial Black\',sans-serif;font-size:22px;font-weight:700;'
        'color:#D4AF37;letter-spacing:-0.01em;margin:0;'
        'text-shadow:0 0 12px rgba(212,175,55,0.3);">'
        f"{title}</h2>"
        "</td></tr>"
        # Golden Thread：1px 渐隐金线分隔
        '<tr><td style="padding:14px 24px 0;">'
        '<div style="height:1px;background:linear-gradient(90deg,rgba(212,175,55,0.6),'
        'rgba(212,175,55,0.1) 50%,transparent);"></div>'
        "</td></tr>"
        # 正文区：Hanken Grotesk
        '<tr><td style="padding:16px 24px 24px;font-family:\'Hanken Grotesk\',-apple-system,'
        '\'PingFang SC\',\'Microsoft YaHei\',sans-serif;font-size:14px;line-height:1.7;color:#e5e2e1;">'
        f"{body_html}"
        "</td></tr>"
        # 底部：系统状态标签
        '<tr><td style="border-top:1px solid rgba(212,175,55,0.15);padding:14px 24px;">'
        '<span style="font-family:\'JetBrains Mono\',\'Courier New\',monospace;font-size:10px;'
        'color:#99907C;letter-spacing:0.15em;">'
        "GOULONG SYSTEM · 照胆"
        "</span>"
        "</td></tr>"
        "</table>"
        "</td></tr>"
        "</table>"
        "</body></html>"
    )


CODE_TTL_SECONDS = 300
RATE_LIMIT_SECONDS = 60
IP_RATE_LIMIT = 10
IP_RATE_WINDOW = 3600
VERIFY_MAX_ATTEMPTS = 5
VERIFY_LOCKOUT_SECONDS = 300

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class EmailRateLimitError(Exception):
    """60 秒内重复请求验证码"""


class EmailInvalidAddressError(Exception):
    """邮箱地址格式错误"""


class EmailSendError(Exception):
    """阿里云邮件推送下发失败"""


def validate_email(email: str) -> bool:
    return bool(email and EMAIL_PATTERN.match(email))


def generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def _rate_key(email: str) -> str:
    return f"EMAIL:rate:{email}"


def _code_key(email: str) -> str:
    return f"EMAIL:code:{email}"


def _verify_attempts_key(email: str) -> str:
    return f"EMAIL:verify:{email}"


def _ip_rate_key(ip: str) -> str:
    return f"EMAIL:rate:ip:{ip}"


_dm_client: Any = None


def _get_dm_client() -> Any:
    """懒加载并复用阿里云 DirectMail Client（模块级单例）。"""
    global _dm_client
    if _dm_client is not None:
        return _dm_client

    from alibabacloud_dm20151123.client import Client as DmClient
    from alibabacloud_tea_openapi import models as open_api_models

    if not settings.aliyun_dm_account_name:
        raise EmailSendError("阿里云邮件推送未配置 aliyun_dm_account_name")

    if not settings.aliyun_access_key_id or not settings.aliyun_access_key_secret:
        raise EmailSendError("阿里云未配置 aliyun_access_key_id/secret")

    config = open_api_models.Config(
        access_key_id=settings.aliyun_access_key_id,
        access_key_secret=settings.aliyun_access_key_secret,
    )
    config.endpoint = "dm.aliyuncs.com"
    _dm_client = DmClient(config)
    return _dm_client


async def _send_via_aliyun(
    to_address: str,
    subject: str,
    html_body: str,
    tag_name: str = "",
) -> str:
    from alibabacloud_dm20151123 import models as dm_models
    from alibabacloud_tea_util import models as util_models

    request = dm_models.SingleSendMailRequest(
        account_name=settings.aliyun_dm_account_name,
        address_type=1,
        reply_to_address="false",
        subject=subject,
        to_address=to_address,
        html_body=html_body,
        from_alias=settings.aliyun_dm_from_alias or "句龙·照胆",
        tag_name=tag_name or None,
    )
    try:
        client = _get_dm_client()
        resp = await client.single_send_mail_with_options_async(request, util_models.RuntimeOptions())
        env_id = resp.body.env_id if resp.body else ""
        logger.info("DirectMail sent to=%s*** env_id=%s", to_address[:3], env_id)
        return env_id
    except Exception as e:
        msg = getattr(e, "message", str(e))
        logger.error("DirectMail send failed to=%s*** err=%s", to_address[:3], msg)
        raise EmailSendError(f"邮件发送失败: {msg}") from e


async def send_verification_code(email: str, ip: str | None = None) -> tuple[str, int]:
    """发送邮箱验证码（身份验证场景）。

    Returns: (code, expires_in_seconds)
    """
    if not validate_email(email):
        raise EmailInvalidAddressError(f"邮箱格式错误: {email}")

    redis = get_redis()

    if ip:
        ip_count = await redis.get(_ip_rate_key(ip))
        if ip_count and int(ip_count) >= IP_RATE_LIMIT:
            raise EmailRateLimitError("该 IP 发送次数过多，请稍后再试")

    if await redis.exists(_rate_key(email)):
        raise EmailRateLimitError("60 秒内重复请求")

    code = settings.email_fixed_code or generate_code()
    if settings.email_fixed_code:
        logger.warning("email_fixed_code is set — using fixed code (development only)")
    else:
        await _send_via_aliyun(
            to_address=email,
            subject="句龙·照胆 — 邮箱验证码",
            html_body=_wrap_email(
                title="邮箱验证",
                body_html=_render("auth_code.html", code=code),
                ref_code="REF.GL-AUTH",
            ),
            tag_name="auth",
        )

    await redis.set(_code_key(email), code, ex=CODE_TTL_SECONDS)
    await redis.set(_rate_key(email), "1", ex=RATE_LIMIT_SECONDS)

    if ip:
        await redis.incr(_ip_rate_key(ip))
        await redis.expire(_ip_rate_key(ip), IP_RATE_WINDOW)

    logger.info("Email code sent: to=%s*** expires_in=%ds", email[:3], CODE_TTL_SECONDS)
    return code, CODE_TTL_SECONDS


async def verify_code(email: str, code: str) -> bool:
    if not validate_email(email):
        return False

    redis = get_redis()

    attempts_key = _verify_attempts_key(email)
    attempts = await redis.get(attempts_key)
    if attempts is not None and int(attempts) >= VERIFY_MAX_ATTEMPTS:
        await redis.delete(_code_key(email))
        return False

    stored = await redis.get(_code_key(email))
    stored_code = stored.decode() if isinstance(stored, bytes) else stored
    if stored_code is None or not hmac.compare_digest(stored_code, code):
        pipe = redis.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, VERIFY_LOCKOUT_SECONDS)
        await pipe.execute()
        return False

    await redis.delete(_code_key(email))
    await redis.delete(attempts_key)
    return True


async def send_payment_notification(
    to_address: str,
    username: str,
    product: str,
    plan: str,
    amount: str,
    expire_date: str,
) -> str | None:
    """支付成功通知。"""
    if not settings.aliyun_dm_account_name:
        logger.info("DirectMail not configured, payment notification skipped")
        return None
    return await _send_via_aliyun(
        to_address=to_address,
        subject=f"支付成功 — {product}",
        html_body=_wrap_email(
            title="支付成功",
            body_html=_render(
                "payment_success.html",
                username=username,
                product=product,
                plan=plan,
                amount=amount,
                expire_date=expire_date,
            ),
            ref_code="REF.GL-PAY",
        ),
        tag_name="payment",
    )


async def send_expire_reminder(
    to_address: str,
    username: str,
    product: str,
    expire_date: str,
    days: int,
) -> str | None:
    """会员到期提醒。"""
    if not settings.aliyun_dm_account_name:
        return None
    return await _send_via_aliyun(
        to_address=to_address,
        subject=f"会员到期提醒 — {product}",
        html_body=_wrap_email(
            title="会员到期提醒",
            body_html=_render(
                "expire_reminder.html",
                username=username,
                product=product,
                expire_date=expire_date,
                days=days,
            ),
            ref_code="REF.GL-EXPR",
        ),
        tag_name="expire",
    )


async def send_notification(
    to_address: str,
    subject: str,
    content: str,
    username: str = "用户",
) -> str | None:
    """通用系统通知。"""
    if not settings.aliyun_dm_account_name:
        return None
    return await _send_via_aliyun(
        to_address=to_address,
        subject=subject,
        html_body=_wrap_email(
            title=subject,
            body_html=_render(
                "notification.html",
                username=username,
                content=content,
            ),
            ref_code="REF.GL-NTC",
        ),
        tag_name="notice",
    )
