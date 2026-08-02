"""FastAPI 应用入口"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.core.config import assert_production_security, settings
from app.core.database import init_db
from app.core.redis_client import close_redis
from app.lib.private_temp import cleanup_private_temp_dir
from app.api.v1.inspection import router as inspection_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.auth import router as auth_router
from app.api.v1.agent import router as agent_router
from app.api.v1.settings import router as settings_router
from app.api.v1.payments import router as payment_router
from app.api.v1.subscriptions import router as subscription_router
from app.api.v1.wechat_callback import router as wechat_callback_router
from app.api.router import router as api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(cleanup_private_temp_dir)
    await init_db()
    assert_production_security()
    yield
    await close_redis()


app = FastAPI(
    title="句龙照胆 — 体检台 API",
    version="0.1.0",
    description="基于 PydanticAI 的工程文档智能体检系统",
    lifespan=lifespan,
)

_MAX_CONTENT_LENGTH = 100 * 1024 * 1024


class _RequestBodyTooLarge(Exception):
    """请求体在接收过程中超过允许大小。"""


@app.middleware("http")
async def max_body_size_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Content-Length 无效"})
        if declared_length < 0:
            return JSONResponse(status_code=400, content={"detail": "Content-Length 无效"})
        if declared_length > _MAX_CONTENT_LENGTH:
            return JSONResponse(status_code=413, content={"detail": "请求体过大"})

    received_length = 0
    receive = request._receive

    async def limited_receive():
        nonlocal received_length
        message = await receive()
        if message["type"] == "http.request":
            received_length += len(message.get("body", b""))
            if received_length > _MAX_CONTENT_LENGTH:
                raise _RequestBodyTooLarge
        return message

    request._receive = limited_receive
    try:
        return await call_next(request)
    except _RequestBodyTooLarge:
        return JSONResponse(status_code=413, content={"detail": "请求体过大"})


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "frame-src 'self'; "
        "connect-src 'self';"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if "*" in _cors_origins:
    raise RuntimeError("CORS origins 不允许使用 '*' 通配符（allow_credentials=True 时不安全）")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


app.include_router(inspection_router)
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(agent_router)
app.include_router(payment_router)
app.include_router(subscription_router)
app.include_router(wechat_callback_router)
app.include_router(api_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
