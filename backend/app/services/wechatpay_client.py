from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


class WechatPayError(Exception):
    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass
class _PlatformCert:
    serial_no: str
    public_key: Any
    pem: str


@dataclass
class WechatPayConfig:
    app_id: str
    mch_id: str
    api_v3_key: str
    cert_serial_no: str
    private_key_pem: str
    notify_url: str
    public_key_id: str = ""
    public_key_pem: str = ""
    base_url: str = "https://api.mch.weixin.qq.com"


def _load_config() -> WechatPayConfig:
    pem = settings.wechatpay_private_key_pem or ""
    if not pem and settings.wechatpay_private_key_path:
        with open(settings.wechatpay_private_key_path, encoding="utf-8") as f:
            pem = f.read()
    public_key_pem = ""
    if settings.wechatpay_public_key_path and os.path.exists(settings.wechatpay_public_key_path):
        with open(settings.wechatpay_public_key_path, encoding="utf-8") as f:
            public_key_pem = f.read()
    return WechatPayConfig(
        app_id=settings.wechatpay_app_id,
        mch_id=settings.wechatpay_mch_id,
        api_v3_key=settings.wechatpay_api_v3_key,
        cert_serial_no=settings.wechatpay_cert_serial_no,
        private_key_pem=pem,
        notify_url=settings.wechatpay_notify_url,
        public_key_id=settings.wechatpay_public_key_id,
        public_key_pem=public_key_pem,
    )


class WechatPayClient:
    def __init__(self, config: WechatPayConfig | None = None) -> None:
        self._config = config or _load_config()
        key = serialization.load_pem_private_key(
            self._config.private_key_pem.encode(), password=None
        )
        if not isinstance(key, RSAPrivateKey):
            raise WechatPayError("商户 API 证书私钥必须是 RSA 密钥")
        self._private_key: RSAPrivateKey = key
        self._platform_certs: dict[str, _PlatformCert] = {}
        self._wechatpay_public_key: _PlatformCert | None = None
        if self._config.public_key_pem:
            public_key = serialization.load_pem_public_key(
                self._config.public_key_pem.encode()
            )
            if not isinstance(public_key, RSAPublicKey):
                raise WechatPayError("微信支付公钥必须是 RSA 公钥")
            self._wechatpay_public_key = _PlatformCert(
                serial_no=self._config.public_key_id,
                public_key=public_key,
                pem=self._config.public_key_pem,
            )
            if self._config.public_key_id:
                self._platform_certs[self._config.public_key_id] = self._wechatpay_public_key
        self._client = httpx.AsyncClient(timeout=30.0)

    def _generate_nonce(self) -> str:
        import secrets

        return secrets.token_hex(16).upper()

    def _sign(self, message: str) -> str:
        signature = self._private_key.sign(
            message.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def _build_authorization(self, method: str, url: str, body: str) -> str:
        timestamp = str(int(time.time()))
        nonce = self._generate_nonce()
        sign_str = f"{method}\n{url}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._sign(sign_str)
        return (
            f'WECHATPAY2-SHA256-RSA2048 mchid="{self._config.mch_id}",'
            f'nonce_str="{nonce}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{self._config.cert_serial_no}"'
        )

    async def _request(
        self, method: str, path: str, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = json.dumps(json_body, separators=(",", ":"), ensure_ascii=False) if json_body else ""
        authorization = self._build_authorization(method, path, body)
        headers = {
            "Authorization": authorization,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        resp = await self._client.request(
            method, f"{self._config.base_url}{path}", headers=headers, content=body
        )
        if resp.status_code >= 400:
            try:
                err = resp.json()
            except Exception:
                err = {"message": resp.text}
            raise WechatPayError(
                err.get("message", "微信支付请求失败"),
                code=err.get("code"),
                status_code=resp.status_code,
            )
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def create_native_order(
        self,
        *,
        out_trade_no: str,
        description: str,
        amount_cents: int,
        client_ip: str,
        attach: str = "",
    ) -> str:
        payload: dict[str, Any] = {
            "appid": self._config.app_id,
            "mchid": self._config.mch_id,
            "description": description,
            "out_trade_no": out_trade_no,
            "notify_url": self._config.notify_url,
            "amount": {"total": amount_cents, "currency": "CNY"},
            "scene_info": {"payer_client_ip": client_ip},
        }
        if attach:
            payload["attach"] = attach[:128]
        result = await self._request("POST", "/v3/pay/transactions/native", payload)
        code_url = result.get("code_url")
        if not code_url:
            raise WechatPayError("微信支付未返回 code_url")
        return str(code_url)

    async def query_order(self, out_trade_no: str) -> dict[str, Any]:
        path = f"/v3/pay/transactions/out-trade-no/{out_trade_no}?mchid={self._config.mch_id}"
        return await self._request("GET", path)

    async def close_order(self, out_trade_no: str) -> None:
        path = f"/v3/pay/transactions/out-trade-no/{out_trade_no}/close"
        await self._request("POST", path, {"mchid": self._config.mch_id})

    async def _download_platform_certs(self) -> None:
        resp = await self._request("GET", "/v3/certificates")
        for item in resp.get("data", []):
            serial_no = item.get("serial_no", "")
            resource = item.get("decrypt_resource") or item.get("resource", {})
            pem = self._decrypt_resource(resource)
            cert = x509.load_pem_x509_certificate(pem.encode())
            self._platform_certs[serial_no] = _PlatformCert(
                serial_no=serial_no,
                public_key=cert.public_key(),
                pem=pem,
            )

    def _decrypt_resource(self, resource: dict[str, str]) -> str:
        nonce = resource.get("nonce", "")
        ciphertext = resource.get("ciphertext", "")
        associated_data = resource.get("associated_data", "")
        aesgcm = AESGCM(self._config.api_v3_key.encode())
        plaintext = aesgcm.decrypt(
            nonce.encode(),
            base64.b64decode(ciphertext),
            associated_data.encode() if associated_data else None,
        )
        return plaintext.decode()

    def decrypt_callback(self, resource: dict[str, str]) -> dict[str, Any]:
        plaintext = self._decrypt_resource(resource)
        return json.loads(plaintext)

    def verify_callback(
        self,
        *,
        timestamp: str,
        nonce: str,
        body: str,
        signature_b64: str,
        serial: str,
    ) -> bool:
        cert = self._platform_certs.get(serial) or self._wechatpay_public_key
        if cert is None:
            return False
        try:
            ts_int = int(timestamp)
        except (ValueError, TypeError):
            return False
        if abs(int(time.time()) - ts_int) > 300:
            return False
        sign_str = f"{timestamp}\n{nonce}\n{body}\n"
        signature = base64.b64decode(signature_b64)
        try:
            cert.public_key.verify(
                signature,
                sign_str.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    async def ensure_platform_cert(self, serial: str | None = None) -> None:
        if serial and serial in self._platform_certs:
            return
        if self._wechatpay_public_key is not None:
            return
        if not self._platform_certs:
            await self._download_platform_certs()


_client_instance: WechatPayClient | None = None


def get_wechatpay_client() -> WechatPayClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = WechatPayClient()
    return _client_instance


def reset_wechatpay_client() -> None:
    global _client_instance
    _client_instance = None
