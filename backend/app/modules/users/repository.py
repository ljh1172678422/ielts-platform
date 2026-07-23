"""用户模块 SQLAlchemy 查询封装 (system-architecture §3)。

单表或单聚合根操作。Phase 4.4-4.6 填充。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserGoal


async def get_goals_by_user(
    db: AsyncSession, user_id: int, status: str | None = None
) -> list[UserGoal]:
    """查询用户目标列表（含未软删过滤，按 created_at DESC）。"""
    stmt = select(UserGoal).where(
        UserGoal.user_id == user_id, UserGoal.deleted_at.is_(None)
    )
    if status is not None:
        stmt = stmt.where(UserGoal.status == status)
    stmt = stmt.order_by(UserGoal.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_goal_by_id(
    db: AsyncSession, goal_id: int, user_id: int
) -> UserGoal | None:
    """按 id 查目标，校验属于该用户且未软删。"""
    stmt = select(UserGoal).where(
        UserGoal.id == goal_id,
        UserGoal.user_id == user_id,
        UserGoal.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_goal(db: AsyncSession, user_id: int) -> UserGoal | None:
    """查用户当前 active 目标（ADR-014：同时仅一个）。"""
    stmt = select(UserGoal).where(
        UserGoal.user_id == user_id,
        UserGoal.status == "active",
        UserGoal.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
