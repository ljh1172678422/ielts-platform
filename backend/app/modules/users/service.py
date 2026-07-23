"""用户模块业务逻辑 (users.md §2-§7)。

事务边界 + 跨表约束校验：
- get_me: 返回当前用户公开信息（含 profile + created_at）
- update_profile: 事务内 UPDATE user_profiles(nickname/avatar_url/timezone)
- update_password: 旧密码校验 → 新密码哈希更新
- goals CRUD: ADR-014 active 唯一约束
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.user import User, UserProfile
from app.modules.users.schemas import (
    ProfileUpdateRequest,
    UserProfilePublic,
    UserPublic,
)


def build_user_public(user: User) -> UserPublic:
    """从 ORM User 构造 UserPublic（id 转 str，ADR-025）。

    被 auth 模块与 users 模块共用，定义在此避免循环导入。
    """
    profile = user.profile
    return UserPublic(
        id=str(user.id),
        email=user.email,
        role=user.role.name,
        status=user.status,
        profile=UserProfilePublic(
            nickname=profile.nickname if profile else None,
            timezone=profile.timezone if profile else "Asia/Shanghai",
            avatar_url=profile.avatar_url if profile else None,
        ),
        created_at=user.created_at,
    )


async def get_me(db: AsyncSession, user_id: int) -> UserPublic:
    """获取当前用户公开信息 (users.md §2)。

    get_current_user 已校验 token + 状态，此处仅需 JOIN profile。
    """
    stmt = (
        select(User)
        .options(selectinload(User.role), selectinload(User.profile))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        # 正常不应发生（get_current_user 已过滤），兜底
        raise AppError(code=2005, message="账号不可用", http_status=401)
    return build_user_public(user)


async def update_profile(
    db: AsyncSession, user_id: int, req: ProfileUpdateRequest
) -> UserPublic:
    """修改资料 (users.md §3)。

    全量替换 profile 字段；未提供则置 null（nickname/avatar_url）。
    timezone 必填，Pydantic 已校验 IANA 合法性。
    """
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile is None:
        raise AppError(
            code=9000,
            message="系统内部错误",
            http_status=500,
            details=[{"field": "profile", "message": "profile not found"}],
        )

    profile.nickname = req.nickname
    profile.avatar_url = req.avatar_url
    profile.timezone = req.timezone
    await db.flush()

    # 重新查 user 以拿到 role + 更新后的 profile
    user_stmt = (
        select(User)
        .options(selectinload(User.role), selectinload(User.profile))
        .where(User.id == user_id)
    )
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one()
    return build_user_public(user)


async def update_password(
    db: AsyncSession,
    user_id: int,
    old_password: str,
    new_password: str,
) -> None:
    """修改密码 (users.md §4)。

    旧密码错误 → 3003/400。新密码 != 旧密码由 Pydantic 校验。
    不返回新 token（ADR-027 无状态）。
    """
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(code=2005, message="账号不可用", http_status=401)

    # 旧密码校验 → 失败 3003（users.md §4.3）
    if not verify_password(old_password, user.password_hash):
        raise AppError(
            code=3003,
            message="旧密码错误",
            http_status=400,
        )

    user.password_hash = hash_password(new_password)
    await db.flush()
