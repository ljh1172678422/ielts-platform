"""Admin 模块 Pydantic schemas（对齐 admin.md §8 DTO 速查）。

id 序列化为 str（ADR-025），全部 snake_case（ADR-026）。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Dashboard（admin.md §2.2）
# ---------------------------------------------------------------------------


class DashboardUsers(BaseModel):
    total: int
    active_today: int
    new_this_week: int


class DashboardQuestions(BaseModel):
    total: int
    published: int
    draft: int
    disabled: int


class DashboardPractice(BaseModel):
    total_sessions: int
    total_attempts: int
    total_recordings: int
    total_duration_seconds: int


class DashboardTopics(BaseModel):
    total: int


class DashboardTags(BaseModel):
    total: int


class DashboardData(BaseModel):
    users: DashboardUsers
    questions: DashboardQuestions
    practice: DashboardPractice
    topics: DashboardTopics
    tags: DashboardTags


# ---------------------------------------------------------------------------
# 用户管理（admin.md §3）
# ---------------------------------------------------------------------------


class AdminUserListItem(BaseModel):
    id: str
    email: str
    role: str
    status: str
    nickname: str | None
    last_login_at: datetime | None
    created_at: datetime


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


# ---------------------------------------------------------------------------
# 主题 CRUD（admin.md §4）
# ---------------------------------------------------------------------------


class AdminTopicItem(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    question_count: int
    is_system: bool
    created_at: datetime


class TopicUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    slug: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=200)


# ---------------------------------------------------------------------------
# 标签 CRUD（admin.md §5）
# ---------------------------------------------------------------------------


class AdminTagItem(BaseModel):
    id: str
    name: str
    slug: str
    question_count: int
    created_at: datetime


class TagUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    slug: str | None = Field(default=None, max_length=30)


# ---------------------------------------------------------------------------
# 题目 CRUD（admin.md §6）
# ---------------------------------------------------------------------------


class TopicRef(BaseModel):
    id: str
    name: str


class TagRef(BaseModel):
    id: str
    name: str


class AdminQuestionListItem(BaseModel):
    id: str
    part: int
    title: str
    topic: TopicRef
    tags: list[TagRef]
    difficulty: int | None
    status: str
    source_type: str
    source_name: str
    practice_count: int
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class AdminQuestionDetail(AdminQuestionListItem):
    content: str
    cue_card: str | None


class QuestionUpsertRequest(BaseModel):
    part: int = Field(ge=1, le=3)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=5000)
    cue_card: str | None = Field(default=None, max_length=2000)
    topic_id: str
    tag_ids: list[str] = Field(default_factory=list)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    source_type: str = Field(pattern="^(official|historical|mock|custom)$")
    source_name: str = Field(min_length=1, max_length=255)
    # create 默认 draft；update 可传 disabled
    status: str | None = Field(default=None, pattern="^(draft|published|disabled)$")


class UpdateQuestionStatusRequest(BaseModel):
    status: str = Field(pattern="^(draft|published|disabled)$")
