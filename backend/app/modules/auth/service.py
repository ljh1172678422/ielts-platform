"""认证模块业务逻辑 (auth.md §2/§3/§4)。

事务边界 + 跨表约束校验：
- register: 校验邮箱未占用 → bcrypt 哈希 → 事务建 user+profile+log → 签 JWT
- login: 防枚举（统一 3002）→ bcrypt 校验 → 状态检查 → 更新 last_login_at + log → 签 JWT
- logout: 无状态，仅返回成功（ADR-027）
"""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password
from app.models.activity import UserActivityLog
from app.models.user import Role, User, UserProfile
from app.modules.auth.schemas import RegisterRequest
from app.modules.users.schemas import UserProfilePublic, UserPublic


async def _get_role_by_name(db: AsyncSession, name: str) -> Role:
    stmt = select(Role).where(Role.name == name)
    result = await db.execute(stmt)
    role = result.scalar_one_or_none()
    if role is None:
        raise AppError(
            code=9000,
            message="系统内部错误",
            http_status=500,
            details=[{"field": "role", "message": f"role '{name}' not seeded"}],
        )
    return role


def _build_user_public(user: User) -> UserPublic:
    """从 ORM User 构造 UserPublic（id 转 str，ADR-025）。"""
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


async def register(
    db: AsyncSession, req: RegisterRequest, *, ip_address: str | None = None
) -> dict:
    """注册新用户 (auth.md §2.4)。

    返回 AuthData dict（含 user/access_token/expires_in）。
    """
    # 1. 校验 timezone 合法性（与 ProfileUpdateRequest 一致，防绕过）
    try:
        ZoneInfo(req.timezone)
    except ZoneInfoNotFoundError as exc:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "timezone", "message": f"invalid IANA timezone: {req.timezone}"}],
        ) from exc

    # 2. 邮箱是否已注册（仅查未软删账号，auth.md §2.4.2）
    existing = await _get_user_by_email_active(db, req.email)
    if existing is not None:
        raise AppError(
            code=3001,
            message="邮箱已注册",
            http_status=409,
            details=[{"field": "email", "message": "email already registered"}],
        )

    # 3. 取 user 角色
    role = await _get_role_by_name(db, "user")

    # 4. 事务内创建 user + profile + activity log
    nickname = req.nickname or req.email.split("@", 1)[0]
    password_hash = hash_password(req.password)

    user = User(
        email=req.email,
        password_hash=password_hash,
        role_id=role.id,
        status="active",
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()  # 取 user.id

    profile = UserProfile(
        user_id=user.id,
        nickname=nickname,
        timezone=req.timezone,
    )
    db.add(profile)

    log = UserActivityLog(
        user_id=user.id,
        action="user_registered",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
    )
    db.add(log)
    await db.flush()

    # 5. 签发 JWT
    token, expires_in = create_access_token(
        user_id=user.id, role=role.name, email=user.email
    )

    # 6. 构造响应（profile 关系需手动 attach，因刚 flush 未刷新关系）
    user.profile = profile
    user.role = role
    user_public = _build_user_public(user)

    return {
        "user": user_public.model_dump(mode="json"),
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


async def _get_user_by_email_active(db: AsyncSession, email: str) -> User | None:
    """查未软删账号（注册冲突检查）。"""
    stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
