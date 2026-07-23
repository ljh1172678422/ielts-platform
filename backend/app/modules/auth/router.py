"""认证模块路由 (auth.md §2/§3/§4)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import success
from app.models.user import User
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=None)
async def register(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """注册新账号 (auth.md §2)。

    成功 HTTP 200，返回 {code:0, message:"ok", data: AuthData}。
    错误：3001 邮箱已注册 / 1001 参数校验失败。
    """
    ip = request.client.host if request.client else None
    data = await service.register(db, req, ip_address=ip)
    return success(data)


@router.post("/login", response_model=None)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """登录 (auth.md §3)。

    成功 HTTP 200，返回 {code:0, message:"ok", data: AuthData}。
    错误：3002 邮箱或密码错误（防枚举）/ 2004 账号已禁用。
    """
    ip = request.client.host if request.client else None
    data = await service.login(db, req, ip_address=ip)
    return success(data)


@router.post("/logout", response_model=None)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """退出登录 (auth.md §4)。

    MVP 无状态退出（ADR-027）：仅写日志，不撤销 token。
    成功 HTTP 200，data=null。
    鉴权失败：2001/2002 由 get_current_user 抛出。
    """
    ip = request.client.host if request.client else None
    await service.logout(db, current_user.id, ip_address=ip)
    return success(None)
