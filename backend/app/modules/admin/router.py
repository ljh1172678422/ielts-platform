"""Admin 模块路由（admin.md §1.2）。

所有 /admin/* 需 Bearer token + role='admin'（admin.md §1.1）。
Phase 5.1：Dashboard。后续 5.2-5.5 追加用户/主题/标签/题目路由。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.exceptions import success
from app.models.user import User
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import UpdateUserStatusRequest

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


# ---------------------------------------------------------------------------
# 用户管理（admin.md §3）
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(active|disabled)$"),
    role: str | None = Query(default=None, pattern="^(user|admin)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """用户列表（分页+筛选，admin.md §3.1）。"""
    data = await admin_service.list_users(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        role=role,
    )
    return success(data)


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    req: UpdateUserStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """启用/禁用用户（admin.md §3.2，8006/8007 防自锁/防互操作）。"""
    data = await admin_service.update_user_status(
        db,
        target_id=user_id,
        new_status=req.status,
        current_user=current_user,
    )
    return success(data)
