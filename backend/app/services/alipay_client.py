from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config import settings


class AlipayError(Exception):
    pass


@dataclass
class AlipayConfig:
    app_id: str
    seller_id: str
    gateway_url: str
    sign_type: str
    private_key_path: str
    public_key_path: str
    notify_url: str
    return_url: str


def _read_key(path: str, header: str, footer: str) -> str:
    with open(path, encoding="utf-8") as f:
        value = f.read().strip()
    if "-----BEGIN" in value:
        return value
    return f"{header}\n{value}\n{footer}\n"


def _load_config() -> AlipayConfig:
    return AlipayConfig(
        app_id=settings.alipay_app_id,
        seller_id=settings.alipay_seller_id,
        gateway_url=settings.alipay_gateway_url.rstrip("?"),
        sign_type=settings.alipay_sign_type or "RSA2",
        private_key_path=settings.alipay_private_key_path,
        public_key_path=settings.alipay_public_key_path,
        notify_url=settings.alipay_notify_url,
        return_url=settings.alipay_zhaodan_return_url,
    )


class AlipayClient:
    def __init__(self, config: AlipayConfig | None = None) -> None:
        self._config = config or _load_config()
        if self._config.sign_type != "RSA2":
            raise AlipayError("支付宝仅支持 RSA2 签名")
        private_pem = _read_key(
            self._config.private_key_path,
            "-----BEGIN PRIVATE KEY-----",
            "-----END PRIVATE KEY-----",
        )
        public_pem = _read_key(
            self._config.public_key_path,
            "-----BEGIN PUBLIC KEY-----",
            "-----END PUBLIC KEY-----",
        )
        private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
        public_key = serialization.load_pem_public_key(public_pem.encode())
        if not isinstance(private_key, RSAPrivateKey):
            raise AlipayError("支付宝应用私钥必须是 RSA 私钥")
        if not isinstance(public_key, RSAPublicKey):
            raise AlipayError("支付宝公钥必须是 RSA 公钥")
        self._private_key = private_key
        self._public_key = public_key

    @property
    def seller_id(self) -> str:
        return self._config.seller_id

    @property
    def app_id(self) -> str:
        return self._config.app_id

    def build_page_pay_url(
        self,
        *,
        out_trade_no: str,
        subject: str,
        total_amount: Decimal,
        passback_params: str = "",
    ) -> str:
        biz_content: dict[str, Any] = {
            "out_trade_no": out_trade_no,
            "total_amount": f"{total_amount:.2f}",
            "subject": subject[:256],
            "product_code": "FAST_INSTANT_TRADE_PAY",
        }
        if passback_params:
            biz_content["passback_params"] = passback_params[:512]
        params = {
            "app_id": self._config.app_id,
            "method": "alipay.trade.page.pay",
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": self._config.sign_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "notify_url": self._config.notify_url,
            "return_url": self._config.return_url,
            "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":")),
        }
        params["sign"] = self._sign(_canonicalize(params))
        return f"{self._config.gateway_url}?{urlencode(params)}"

    def verify_notify(self, params: dict[str, str]) -> bool:
        signature = params.get("sign", "")
        if not signature:
            return False
        data = {k: v for k, v in params.items() if k not in {"sign", "sign_type"}}
        try:
            self._public_key.verify(
                base64.b64decode(signature),
                _canonicalize(data).encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception:
            return False
        return True

    def _sign(self, message: str) -> str:
        signature = self._private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()


def _canonicalize(params: dict[str, str]) -> str:
    return "&".join(f"{key}={params[key]}" for key in sorted(params) if params[key] != "")


def get_alipay_client() -> AlipayClient:
    return AlipayClient()
