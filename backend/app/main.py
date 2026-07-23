"""FastAPI application entry point.

阶段 1 (development-plan 1.5) 验收：uvicorn 启动返回 /health 200。
业务路由在阶段 3+ 挂载。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers, success
from app.modules import auth_router, users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """应用生命周期。Phase 2+ 在此初始化 DB 连接池预热等。"""
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="IELTS Speaking API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # 业务路由统一挂载到 /api/v1（common.md §1）
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, Any]:
        """健康检查，不依赖 DB（避免无 DB 时启动失败）。"""
        return success({"status": "ok"})

    return app


app = create_app()
