"""Home 模块路由（home.md §1.2）。

单接口 GET /home/overview，需 Bearer token。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import success
from app.models.user import User
from app.modules.home import service as home_service

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/overview")
async def get_overview(
    recommendation_limit: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """首页聚合（home.md §2，5 级推荐短路）。"""
    data = await home_service.get_overview(
        db, current_user=current_user, recommendation_limit=recommendation_limit
    )
    return success(data)
