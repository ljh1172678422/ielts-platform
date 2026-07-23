"""认证模块 Pydantic schemas (auth.md §2/§3)。

对齐 auth.md v0.1 §2.2 响应结构：
- data.user: UserPublic (id/email/role/status/profile) —— 复用 users 模块 UserPublic
- data.access_token / token_type / expires_in

字段 snake_case（ADR-026），email 由 Pydantic EmailStr 校验格式。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.schemas import UserPublic


class RegisterRequest(BaseModel):
    """注册请求 (auth.md §2.1)。

    nickname 缺省取 email 本地部分，timezone 缺省 Asia/Shanghai（service 层填充）。
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    nickname: str | None = Field(default=None, max_length=100)
    timezone: str = Field(default="Asia/Shanghai", max_length=50)


class LoginRequest(BaseModel):
    """登录请求 (auth.md §3.1)。"""

    email: EmailStr
    password: str = Field(min_length=1, max_length=64)


class AuthData(BaseModel):
    """注册/登录成功响应 data (auth.md §2.2)。"""

    user: UserPublic
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutData(BaseModel):
    """退出响应 data (auth.md §4.2)。恒为 null（无状态），此模型仅用于文档。"""

    model_config = ConfigDict(json_schema_extra={"example": None})
