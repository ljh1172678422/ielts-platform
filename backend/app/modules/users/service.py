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
from app.models.activity import UserActivityLog
from app.models.user import User, UserGoal, UserProfile
from app.modules.users.repository import (
    get_active_goal,
    get_goal_by_id,
    get_goals_by_user,
)
from app.modules.users.schemas import (
    GoalsResponse,
    ProfileUpdateRequest,
    UserGoalCreate,
    UserGoalPublic,
    UserGoalUpdate,
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


def _goal_to_public(goal: UserGoal) -> UserGoalPublic:
    """UserGoal ORM → UserGoalPublic（id 转 str）。"""
    return UserGoalPublic(
        id=str(goal.id),
        target_score=float(goal.target_score) if goal.target_score is not None else None,
        current_level=goal.current_level,
        exam_date=goal.exam_date,
        daily_goal_minutes=goal.daily_goal_minutes,
        weekly_goal_minutes=goal.weekly_goal_minutes,
        status=goal.status,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


async def list_goals(
    db: AsyncSession, user_id: int, status_filter: str | None = None
) -> GoalsResponse:
    """获取目标列表 (users.md §5)。

    返回 {current, history}：current = 第一条 active，history = 其余按 updated_at DESC。
    """
    goals = await get_goals_by_user(db, user_id, status=status_filter)
    current = None
    history = []
    for g in goals:
        if g.status == "active" and current is None:
            current = _goal_to_public(g)
        else:
            history.append(_goal_to_public(g))
    # history 按 updated_at DESC（repository 已按 created_at DESC，再排一次 updated_at）
    history.sort(key=lambda x: x.updated_at, reverse=True)
    return GoalsResponse(current=current, history=history)


async def create_goal(
    db: AsyncSession, user_id: int, req: UserGoalCreate
) -> UserGoalPublic:
    """创建目标 (users.md §6)。

    已存在 active → 1004/409。至少一字段非空。写 goal_created 日志。
    """
    # 至少一字段非空（users.md §6.1）
    fields = req.model_dump()
    if all(v is None for v in fields.values()):
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "body", "message": "at least one field required"}],
        )

    # ADR-014: 已存在 active 目标 → 1004
    existing = await get_active_goal(db, user_id)
    if existing is not None:
        raise AppError(
            code=1004,
            message="已存在 active 目标",
            http_status=409,
            details=[{"field": "status", "message": "active goal already exists"}],
        )

    goal = UserGoal(
        user_id=user_id,
        target_score=req.target_score,
        current_level=req.current_level,
        exam_date=req.exam_date,
        daily_goal_minutes=req.daily_goal_minutes,
        weekly_goal_minutes=req.weekly_goal_minutes,
        status="active",
    )
    db.add(goal)
    await db.flush()

    log = UserActivityLog(
        user_id=user_id,
        action="goal_created",
        entity_type="user_goal",
        entity_id=goal.id,
    )
    db.add(log)
    await db.flush()

    return _goal_to_public(goal)


async def update_goal(
    db: AsyncSession,
    user_id: int,
    goal_id: int,
    req: UserGoalUpdate,
) -> UserGoalPublic:
    """更新目标 (users.md §7)。

    goal 不存在/不属于用户 → 1002/404。
    改回 active 且已有其他 active → 1004/409。
    status 变化 → 写 goal_updated 日志。
    """
    goal = await get_goal_by_id(db, goal_id, user_id)
    if goal is None:
        raise AppError(
            code=1002,
            message="目标不存在",
            http_status=404,
        )

    old_status = goal.status

    # 若改为 active 且原非 active → 检查是否已有其他 active
    if req.status == "active" and old_status != "active":
        existing_active = await get_active_goal(db, user_id)
        if existing_active is not None and existing_active.id != goal.id:
            raise AppError(
                code=1004,
                message="已存在 active 目标",
                http_status=409,
                details=[{"field": "status", "message": "another active goal exists"}],
            )

    # 全量替换（status 必填）
    goal.target_score = req.target_score
    goal.current_level = req.current_level
    goal.exam_date = req.exam_date
    goal.daily_goal_minutes = req.daily_goal_minutes
    goal.weekly_goal_minutes = req.weekly_goal_minutes
    goal.status = req.status
    await db.flush()

    # status 变化 → 写日志
    if old_status != goal.status:
        log = UserActivityLog(
            user_id=user_id,
            action="goal_updated",
            entity_type="user_goal",
            entity_id=goal.id,
        )
        db.add(log)
        await db.flush()

    return _goal_to_public(goal)
