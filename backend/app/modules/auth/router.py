"""认证模块路由 (auth.md §2/§3/§4)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import success
from app.modules.auth import service
from app.modules.auth.schemas import RegisterRequest

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
