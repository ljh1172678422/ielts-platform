"""用户模块 Pydantic schemas (users.md §2-§6, auth.md §7.2 DTO)。

对齐 auth.md §7.2 复用 DTO + users.md 各接口扩展：
- UserProfilePublic: nickname / timezone / avatar_url
- UserPublic: id(str) / email / role / status / profile + created_at 扩展
- ProfileUpdateRequest: nickname / avatar_url / timezone(IANA 校验)
- PasswordUpdateRequest: old_password / new_password
- UserGoalCreate / UserGoalUpdate / UserGoalPublic
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserProfilePublic(BaseModel):
    """用户资料公开字段 (auth.md §7.2)。"""

    model_config = ConfigDict(from_attributes=True)

    nickname: str | None = None
    timezone: str
    avatar_url: str | None = None


class UserPublic(BaseModel):
    """用户公开信息 (auth.md §7.2 + users.md §2.2 created_at 扩展)。

    id 为字符串（ADR-025）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    status: str
    profile: UserProfilePublic
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    """修改资料请求 (users.md §3.1)。

    全量替换：未提供字段置 null（nickname/avatar_url），timezone 必填。
    """

    nickname: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    timezone: str = Field(min_length=1, max_length=50)

    @field_validator("timezone")
    @classmethod
    def _validate_iana_timezone(cls, v: str) -> str:
        """校验 IANA 时区名合法性（users.md §3.4，失败 → 1001/422）。"""
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"invalid IANA timezone: {v}") from exc
        return v

    @field_validator("avatar_url")
    @classmethod
    def _validate_avatar_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("avatar_url must be http(s) URL")
        return v


class PasswordUpdateRequest(BaseModel):
    """修改密码请求 (users.md §4.1)。"""

    old_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)

    @field_validator("new_password")
    @classmethod
    def _validate_new_diff(cls, v: str, info) -> str:
        """new_password != old_password（users.md §4.3 1001）。"""
        old = info.data.get("old_password")
        if old is not None and v == old:
            raise ValueError("new_password must differ from old_password")
        return v


class UserGoalCreate(BaseModel):
    """创建目标请求 (users.md §6.1)。"""

    target_score: float | None = Field(default=None, ge=0, le=9)
    current_level: str | None = Field(default=None, max_length=20)
    exam_date: date | None = None
    daily_goal_minutes: int | None = Field(default=None, ge=0)
    weekly_goal_minutes: int | None = Field(default=None, ge=0)


class UserGoalUpdate(BaseModel):
    """更新目标请求 (users.md §7.1)，全量替换，status 必填。"""

    target_score: float | None = Field(default=None, ge=0, le=9)
    current_level: str | None = Field(default=None, max_length=20)
    exam_date: date | None = None
    daily_goal_minutes: int | None = Field(default=None, ge=0)
    weekly_goal_minutes: int | None = Field(default=None, ge=0)
    status: str = Field(pattern="^(active|achieved|archived)$")


class UserGoalPublic(BaseModel):
    """目标公开信息。id 为字符串（ADR-025）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    target_score: float | None
    current_level: str | None
    exam_date: date | None
    daily_goal_minutes: int | None
    weekly_goal_minutes: int | None
    status: str
    created_at: datetime
    updated_at: datetime


class GoalsResponse(BaseModel):
    """目标列表响应 (users.md §5.2)。current + history，非分页。"""

    current: UserGoalPublic | None
    history: list[UserGoalPublic]
