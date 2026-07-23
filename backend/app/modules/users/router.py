"""用户模块路由 (users.md §2-§7)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import success
from app.models.user import User
from app.modules.users import service
from app.modules.users.schemas import PasswordUpdateRequest, ProfileUpdateRequest

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
