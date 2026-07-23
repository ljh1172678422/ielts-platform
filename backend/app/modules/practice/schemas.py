"""Practice 模块 Pydantic schemas（对齐 practice.md §10 DTO 速查）。

id 序列化为 str（ADR-025），全部 snake_case（ADR-026）。
Phase 7 覆盖会话/attempt 状态机；录音 DTO 声明完整但 Phase 8 才写入
（Phase 7 GET 会话时 recording 恒为 None）。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 请求 DTO（practice.md §10.1）
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """创建练习会话（practice.md §2.1）。"""

    mode: str = Field(pattern="^(random|topic|part)$")
    part: int | None = Field(default=None, ge=1, le=3)
    topic_id: str | None = None
    question_count: int = Field(ge=1, le=50)


class CreateAttemptRequest(BaseModel):
    """创建答题尝试（practice.md §4.1）。"""

    session_question_id: str


class UpdateAttemptRequest(BaseModel):
    """更新答题状态（practice.md §5.1）。

    status 仅允许 recording/skipped/failed；submitted 只能由录音上传事务设置
    （ADR-015）。传 submitted 由 service 层判 1001（非法参数）。
    """

    status: str = Field(pattern="^(recording|skipped|failed|submitted)$")


# ---------------------------------------------------------------------------
# 响应 DTO（practice.md §10.2）
# ---------------------------------------------------------------------------


class RecordingDTO(BaseModel):
    """录音（practice.md §3.2，Phase 8 写入，Phase 7 恒为 None）。"""

    id: str
    status: str
    mime_type: str
    duration_seconds: int | None
    file_size: int | None
    created_at: datetime


class AttemptDTO(BaseModel):
    """答题尝试（practice.md §3.2/§4.2）。"""

    id: str
    session_question_id: str
    attempt_number: int
    status: str
    started_at: datetime | None
    submitted_at: datetime | None
    duration_seconds: int | None
    recording: RecordingDTO | None


class SessionQuestionDTO(BaseModel):
    """会话题目（含 snapshot 与 attempts，practice.md §2.2）。"""

    id: str
    session_id: str
    question_id: str
    sort_order: int
    snapshot: dict
    attempts: list[AttemptDTO]


class PracticeSessionDTO(BaseModel):
    """练习会话（practice.md §2.2）。"""

    id: str
    status: str
    mode: str
    part_filter: int | None
    topic_filter: str | None
    question_count: int
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    created_at: datetime
    updated_at: datetime
    questions: list[SessionQuestionDTO]
