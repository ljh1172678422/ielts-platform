"""FastAPI 依赖注入（system-architecture §3.4）。

对齐 auth.md §4 / common.md §3.2：
- get_current_user: 从 Authorization: Bearer <token> 解析当前用户。
  - 缺失/格式错 → AppError(2001, 401) "未登录"
  - token 无效 → AppError(2002, 401) "token 无效或已过期"
  - 用户不存在/软删/禁用 → AppError(2005, 401) "账号不可用"
- require_admin: 在 get_current_user 基础上要求 role=admin，
  否则 AppError(2003, 403) "无权限"。
- get_db: 复用 app.core.database（重导出，路由层单一导入路径）。
"""
from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models.user import User

__all__ = ["get_db", "get_current_user", "require_admin"]


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析 Bearer token，返回当前已登录且有效的 User 实体。

    依次校验：Header 存在 → 格式 Bearer → token 解码 → 用户存在 → 未软删 → 未禁用。
    """
    # 1. Header 存在性
    if not authorization:
        raise AppError(
            code=2001,
            message="未登录",
            http_status=401,
            details=[{"field": "authorization", "message": "missing header"}],
        )

    # 2. Bearer 格式
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise AppError(
            code=2001,
            message="未登录",
            http_status=401,
            details=[{"field": "authorization", "message": "expected 'Bearer <token>'"}],
        )
    token = parts[1]

    # 3. token 解码（decode_access_token 内部失败抛 2002/401）
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AppError(
            code=2002,
            message="token 无效或已过期",
            http_status=401,
            details=[{"field": "token", "message": "invalid sub claim"}],
        ) from exc

    # 4. 用户存在 + 未软删
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(
            code=2005,
            message="账号不可用",
            http_status=401,
            details=[{"field": "user", "message": "user not found or deleted"}],
        )

    # 5. 账号未禁用
    if user.status != "active":
        raise AppError(
            code=2005,
            message="账号不可用",
            http_status=401,
            details=[{"field": "status", "message": f"account {user.status}"}],
        )

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前用户角色为 admin，否则 2003/403。"""
    if current_user.role.name != "admin":
        raise AppError(
            code=2003,
            message="无权限",
            http_status=403,
            details=[{"field": "role", "message": "admin role required"}],
        )
    return current_user
