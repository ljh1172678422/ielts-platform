"""认证模块 SQLAlchemy 查询封装 (system-architecture §3)。

单表或单聚合根操作，不含业务规则。Phase 4.1-4.3 填充。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role, User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """按邮箱查用户（含未软删过滤）。"""
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """按 id 查用户（含未软删过滤）。"""
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    """按 name 查角色。"""
    stmt = select(Role).where(Role.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
