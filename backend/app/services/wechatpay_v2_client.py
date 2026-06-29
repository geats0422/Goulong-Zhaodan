from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class WechatPayV2Error(Exception):
    def __init__(self, message: str, *, code: str | None = None, return_code: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.return_code = return_code


@dataclass
class WechatPayV2Config:
    app_id: str
    mch_id: str
    api_v2_key: str
    papay_plan_id: int
    papay_notify_url: str
    papay_deduct_notify_url: str
    base_url: str = "https://api.mch.weixin.qq.com"


def _load_config() -> WechatPayV2Config:
    return WechatPayV2Config(
        app_id=settings.wechatpay_app_id,
        mch_id=settings.wechatpay_mch_id,
        api_v2_key=settings.wechatpay_api_v2_key,
        papay_plan_id=settings.wechatpay_papay_plan_id,
        papay_notify_url=settings.wechatpay_papay_notify_url,
        papay_deduct_notify_url=settings.wechatpay_papay_deduct_notify_url,
    )


def _build_sign(params: dict[str, Any], api_key: str, sign_type: str = "MD5") -> str:
    parts: list[tuple[str, str]] = []
    for k, v in params.items():
        if v is None or v == "" or k == "sign":
            continue
        parts.append((k, str(v)))
    parts.sort(key=lambda x: x[0])
    string_a = "&".join(f"{k}={v}" for k, v in parts)
    string_sign_temp = f"{string_a}&key={api_key}"
    if sign_type == "HMAC-SHA256":
        digest = hmac.new(api_key.encode(), string_sign_temp.encode(), hashlib.sha256).hexdigest()
    else:
        digest = hashlib.md5(string_sign_temp.encode()).hexdigest()
    return digest.upper()


def _to_xml(params: dict[str, Any]) -> str:
    root = ET.Element("xml")
    for k, v in params.items():
        if v is None:
            continue
        child = ET.SubElement(root, k)
        if k == "sign" or v == "":
            child.text = str(v)
        else:
            child.text = f"<![CDATA[{v}]]>" if any(c in str(v) for c in "&<>'\"") else str(v)
    return ET.tostring(root, encoding="unicode")


def _xml_to_dict(xml_text: str) -> dict[str, str]:
    if not xml_text.strip():
        return {}
    root = ET.fromstring(xml_text)
    result: dict[str, str] = {}
    for child in root:
        if child.text is None:
            result[child.tag] = ""
        else:
            text = child.text.strip()
            if text.startswith("<![CDATA[") and text.endswith("]]>"):
                text = text[9:-3]
            result[child.tag] = text
    return result


def _generate_nonce() -> str:
    return "".join(secrets.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz") for _ in range(32))


class WechatPayV2Client:
    def __init__(self, config: WechatPayV2Config | None = None) -> None:
        self._config = config or _load_config()
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=False)

    def _request_serial(self) -> int:
        return int(time.time() * 1000) & 0x7FFFFFFFFFFFFFFF

    def _check_response(self, data: dict[str, str]) -> dict[str, str]:
        if data.get("return_code") != "SUCCESS":
            raise WechatPayV2Error(
                data.get("return_msg", "微信支付 V2 请求失败"),
                return_code=data.get("return_code"),
            )
        if data.get("result_code") and data["result_code"] != "SUCCESS":
            raise WechatPayV2Error(
                data.get("err_code_des", data.get("err_code", "业务失败")),
                code=data.get("err_code"),
            )
        return data

    async def _post_xml(self, path: str, params: dict[str, Any]) -> dict[str, str]:
        if "nonce_str" not in params:
            params["nonce_str"] = _generate_nonce()
        params["sign"] = _build_sign(params, self._config.api_v2_key)
        body = _to_xml(params)
        resp = await self._client.post(
            f"{self._config.base_url}{path}",
            content=body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
        )
        if resp.status_code >= 400:
            raise WechatPayV2Error(f"HTTP {resp.status_code}: {resp.text}")
        return _xml_to_dict(resp.text)

    def build_entrust_url(
        self,
        *,
        contract_code: str,
        contract_display_account: str,
        request_serial: int,
    ) -> str:
        params = {
            "appid": self._config.app_id,
            "mch_id": self._config.mch_id,
            "plan_id": self._config.papay_plan_id,
            "contract_code": contract_code,
            "request_serial": request_serial,
            "contract_display_account": contract_display_account,
            "notify_url": self._config.papay_notify_url,
            "version": "1.0",
            "timestamp": str(int(time.time())),
        }
        sign = _build_sign(params, self._config.api_v2_key)
        params["sign"] = sign
        base = f"{self._config.base_url}/papay/entrustweb"
        return f"{base}?{urlencode(params)}"

    async def query_contract(
        self,
        *,
        contract_id: str | None = None,
        plan_id: int | None = None,
        contract_code: str | None = None,
    ) -> dict[str, str]:
        params: dict[str, Any] = {
            "appid": self._config.app_id,
            "mch_id": self._config.mch_id,
            "version": "1.0",
        }
        if contract_id:
            params["contract_id"] = contract_id
        else:
            params["plan_id"] = plan_id or self._config.papay_plan_id
            params["contract_code"] = contract_code or ""
        return self._check_response(await self._post_xml("/papay/querycontract", params))

    async def delete_contract(
        self,
        *,
        contract_id: str | None = None,
        contract_code: str | None = None,
        remark: str = "用户主动取消订阅",
    ) -> dict[str, str]:
        params: dict[str, Any] = {
            "appid": self._config.app_id,
            "mch_id": self._config.mch_id,
            "version": "1.0",
            "contract_termination_remark": remark,
        }
        if contract_id:
            params["contract_id"] = contract_id
        else:
            params["plan_id"] = self._config.papay_plan_id
            params["contract_code"] = contract_code or ""
        return self._check_response(await self._post_xml("/papay/deletecontract", params))

    async def apply_deduction(
        self,
        *,
        out_trade_no: str,
        contract_id: str,
        body: str,
        total_fee: int,
        client_ip: str,
        attach: str = "",
    ) -> dict[str, str]:
        params: dict[str, Any] = {
            "appid": self._config.app_id,
            "mch_id": self._config.mch_id,
            "body": body,
            "out_trade_no": out_trade_no,
            "total_fee": total_fee,
            "spbill_create_ip": client_ip or "127.0.0.1",
            "notify_url": self._config.papay_deduct_notify_url,
            "trade_type": "PAP",
            "contract_id": contract_id,
        }
        if attach:
            params["attach"] = attach
        return self._check_response(await self._post_xml("/pay/pappayapply", params))

    async def query_order(
        self,
        *,
        transaction_id: str | None = None,
        out_trade_no: str | None = None,
    ) -> dict[str, str]:
        params: dict[str, Any] = {
            "appid": self._config.app_id,
            "mch_id": self._config.mch_id,
        }
        if transaction_id:
            params["transaction_id"] = transaction_id
        elif out_trade_no:
            params["out_trade_no"] = out_trade_no
        else:
            raise ValueError("transaction_id or out_trade_no is required")
        return self._check_response(await self._post_xml("/pay/orderquery", params))

    @staticmethod
    def verify_callback_sign(params: dict[str, str], api_v2_key: str) -> bool:
        expected = params.get("sign", "")
        if not expected:
            return False
        return _build_sign(params, api_v2_key) == expected.upper()

    @staticmethod
    def parse_callback_xml(body: str) -> dict[str, str]:
        return _xml_to_dict(body)


_v2_client_instance: WechatPayV2Client | None = None


def get_wechatpay_v2_client() -> WechatPayV2Client:
    global _v2_client_instance
    if _v2_client_instance is None:
        _v2_client_instance = WechatPayV2Client()
    return _v2_client_instance


def reset_wechatpay_v2_client() -> None:
    global _v2_client_instance
    _v2_client_instance = None
