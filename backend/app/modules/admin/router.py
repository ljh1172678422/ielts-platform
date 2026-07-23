"""Admin 模块路由（admin.md §1.2）。

所有 /admin/* 需 Bearer token + role='admin'（admin.md §1.1）。
Phase 5.1：Dashboard。后续 5.2-5.5 追加用户/主题/标签/题目路由。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.exceptions import success
from app.models.user import User
from app.modules.admin import service as admin_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    # 所有 admin 接口都需管理员鉴权（admin.md §1.1）
    dependencies=[Depends(require_admin)],
)


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """全局统计概览（admin.md §2）。"""
    data = await admin_service.get_dashboard(db)
    return success(data.model_dump())
