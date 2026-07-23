"""用户模块路由 (users.md §2-§7)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import success
from app.models.user import User
from app.modules.users import service
from app.modules.users.schemas import (
    PasswordUpdateRequest,
    ProfileUpdateRequest,
    UserGoalCreate,
    UserGoalUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=None)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取当前用户资料 (users.md §2)。

    成功 HTTP 200，data 为 UserPublic（含 profile + created_at）。
    """
    data = await service.get_me(db, current_user.id)
    return success(data.model_dump(mode="json"))


@router.put("/me", response_model=None)
async def update_me(
    req: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """修改当前用户资料 (users.md §3)。

    全量替换 profile 字段（nickname/avatar_url/timezone）。
    成功 HTTP 200，data 为更新后的 UserPublic。
    错误：1001 timezone 非法 IANA（Pydantic 校验）。
    """
    data = await service.update_profile(db, current_user.id, req)
    return success(data.model_dump(mode="json"))


@router.put("/me/password", response_model=None)
async def update_password(
    req: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """修改密码 (users.md §4)。

    成功 HTTP 200，data=null（不返回新 token，ADR-027）。
    错误：3003 旧密码错误 / 1001 new==old（Pydantic 校验）。
    """
    await service.update_password(
        db, current_user.id, req.old_password, req.new_password
    )
    return success(None)


@router.get("/me/goals", response_model=None)
async def list_goals(
    status: str | None = Query(
        default=None, pattern="^(active|achieved|archived)$"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取目标列表 (users.md §5)。

    成功 HTTP 200，data 为 {current, history}，非分页。
    current = 当前 active 目标（至多 1 个，ADR-014），history = 其余。
    """
    data = await service.list_goals(db, current_user.id, status_filter=status)
    return success(data.model_dump(mode="json"))


@router.post("/me/goals", response_model=None)
async def create_goal(
    req: UserGoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """创建目标 (users.md §6)。

    成功 HTTP 200，data 为新建 Goal（status=active）。
    错误：1004 已存在 active 目标 / 1001 全字段空。
    """
    data = await service.create_goal(db, current_user.id, req)
    return success(data.model_dump(mode="json"))


@router.put("/me/goals/{goal_id}", response_model=None)
async def update_goal(
    goal_id: str,
    req: UserGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """更新目标 (users.md §7)。

    成功 HTTP 200，data 为更新后 Goal。
    错误：1002 目标不存在 / 1004 改回 active 冲突。
    goal_id 为字符串（ADR-025）。
    """
    try:
        gid = int(goal_id)
    except ValueError as exc:
        from app.core.exceptions import AppError

        raise AppError(
            code=1002,
            message="目标不存在",
            http_status=404,
            details=[{"field": "goal_id", "message": "invalid id"}],
        ) from exc
    data = await service.update_goal(db, current_user.id, gid, req)
    return success(data.model_dump(mode="json"))
