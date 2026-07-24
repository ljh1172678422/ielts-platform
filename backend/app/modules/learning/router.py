"""Learning 模块路由（learning.md §1.2）。

所有 /learning 需 Bearer token（learning.md §1.2 全部接口标 Bearer）。
recompute 额外需 admin（learning.md §8 / common.md §3.2 2003）。

Query 参数范围校验：
- days ∈ [1, 90]（learning.md §3.1）
- weeks ∈ [1, 52]（learning.md §4.1）
- months ∈ [1, 24]（learning.md §5.1/§6.1/§7.1）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.exceptions import success
from app.models.user import User
from app.modules.learning import service as learning_service
from app.modules.learning.schemas import (
    DAYS_MAX,
    DAYS_MIN,
    MONTHS_MAX,
    MONTHS_MIN,
    WEEKS_MAX,
    WEEKS_MIN,
    RecomputeRequest,
    validate_days,
    validate_months,
    validate_weeks,
)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """学习概览（learning.md §2）。"""
    data = await learning_service.get_overview(db, current_user=current_user)
    return success(data)


@router.get("/daily")
async def get_daily_trend(
    days: int = Query(default=30, ge=DAYS_MIN, le=DAYS_MAX),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """日趋势（learning.md §3，含今日最近 N 天，补零）。"""
    validate_days(days)
    data = await learning_service.get_daily_trend(
        db, current_user=current_user, days=days
    )
    return success(data)


@router.get("/weekly")
async def get_weekly_trend(
    weeks: int = Query(default=12, ge=WEEKS_MIN, le=WEEKS_MAX),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """周趋势（learning.md §4，ISO 周一~周日，补零）。"""
    validate_weeks(weeks)
    data = await learning_service.get_weekly_trend(
        db, current_user=current_user, weeks=weeks
    )
    return success(data)


@router.get("/monthly")
async def get_monthly_trend(
    months: int = Query(default=12, ge=MONTHS_MIN, le=MONTHS_MAX),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """月趋势（learning.md §5，自然月，补零）。"""
    validate_months(months)
    data = await learning_service.get_monthly_trend(
        db, current_user=current_user, months=months
    )
    return success(data)


@router.get("/topics")
async def get_topics_distribution(
    months: int = Query(default=3, ge=MONTHS_MIN, le=MONTHS_MAX),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """主题分布（learning.md §6，实时从事实表聚合）。"""
    validate_months(months)
    data = await learning_service.get_topics_distribution(
        db, current_user=current_user, months=months
    )
    return success(data)


@router.get("/parts")
async def get_parts_distribution(
    months: int = Query(default=3, ge=MONTHS_MIN, le=MONTHS_MAX),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Part 分布（learning.md §7，实时从事实表聚合）。"""
    validate_months(months)
    data = await learning_service.get_parts_distribution(
        db, current_user=current_user, months=months
    )
    return success(data)


@router.post("/recompute")
async def recompute(
    payload: RecomputeRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """重算 study_records（learning.md §8，admin only，事务 DELETE+INSERT）。"""
    data = await learning_service.recompute(db, admin=admin, payload=payload)
    return success(data)
