"""认证模块 Pydantic schemas (auth.md §2/§3)。

对齐 auth.md v0.1：
- RegisterRequest: email + password + nickname(可选)
- LoginRequest: email + password
- AuthTokenResponse: token + expires_in + token_type
- UserBrief: id(str, ADR-025) + email + role + nickname

字段 snake_case（ADR-026），email 由 Pydantic EmailStr 校验格式。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求 (auth.md §2.1)。"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    nickname: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """登录请求 (auth.md §3.1)。"""

    email: EmailStr
    password: str = Field(min_length=1, max_length=64)


class UserBrief(BaseModel):
    """用户简要信息（注册/登录响应内嵌）。id 为字符串（ADR-025）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    nickname: str | None = None


class AuthTokenResponse(BaseModel):
    """认证 token 响应 (auth.md §2.2/§3.2)。"""

    token: str
    expires_in: int
    token_type: str = "Bearer"
    user: UserBrief
