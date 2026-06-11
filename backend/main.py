"""FastAPI 应用入口"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import init_db
from routers.inspection import router as inspection_router
from routers.knowledge import router as knowledge_router
from routers.auth import router as auth_router
from routers.agent import router as agent_router
from routers.settings import router as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="句龙照胆 — 体检台 API",
    version="0.1.0",
    description="基于 PydanticAI 的工程文档智能体检系统",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inspection_router)
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(agent_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
