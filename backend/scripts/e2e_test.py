"""Phase 3 端到端验证脚本

验证照胆后端 goulong-auth 集成：
  1. POST /auth/register — 写入 goulong_auth.users
  2. POST /auth/login    — 返回 access_token
  3. GET  /auth/me       — 验证 token 解析
  4. GET  /settings/overview — 验证 memberships 配额查询
  5. JWT 解码 — 验证 product=zhaodan

用法：
  uv run uvicorn main:app --host 127.0.0.1 --port 8000 &
  uv run python scripts/e2e_test.py
"""
import asyncio
import base64
import json
import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    email = f"e2e_{uuid.uuid4().hex[:8]}@goulong.dev"
    failures: list[str] = []

    async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
        reg = await c.post(
            "/auth/register",
            json={"email": email, "nickname": "E2E", "password": "Test@12345"},
        )
        print(f"[REGISTER] status={reg.status_code}")
        if reg.status_code not in (200, 201):
            print(f"  body={reg.text[:300]}")
            failures.append("register failed")
            return 1
        rd = reg.json()
        print(f"  id={rd.get('id')} has_token={'access_token' in rd}")

        login = await c.post("/auth/login", json={"email": email, "password": "Test@12345"})
        print(f"[LOGIN] status={login.status_code}")
        if login.status_code != 200:
            print(f"  body={login.text[:300]}")
            failures.append("login failed")
        else:
            ld = login.json()
            login_token = ld["access_token"]
            h = {"Authorization": f"Bearer {login_token}"}

            me = await c.get("/auth/me", headers=h)
            print(f"[ME] status={me.status_code} data={me.json()}")
            if me.status_code != 200:
                failures.append("me failed")

            ov = await c.get("/settings/overview", headers=h)
            print(f"[SETTINGS] status={ov.status_code}")
            if ov.status_code == 200:
                p = ov.json().get("profile", {})
                print(f"  plan={p.get('subscription_plan')} quota={p.get('monthly_quota')} used={p.get('quota_used')} burn={p.get('burn_after_read')}")
            else:
                print(f"  body={ov.text[:300]}")
                failures.append("settings failed")

            parts = login_token.split(".")
            if len(parts) >= 2:
                pb = parts[1] + "=" * (4 - len(parts[1]) % 4)
                payload = json.loads(base64.urlsafe_b64decode(pb))
                print(f"[JWT] product={payload.get('product')} user_id={str(payload.get('user_id', ''))[:8]}...")
                if payload.get("product") != "zhaodan":
                    failures.append("jwt product != zhaodan")

    if failures:
        print(f"\nFAILED: {failures}")
        return 1
    print("\nALL E2E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
