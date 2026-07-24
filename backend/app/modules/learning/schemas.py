"""Learning 模块 Pydantic schemas（对齐 learning.md §10 DTO 速查）。

- id 序列化为 str（ADR-025）
- 全部 snake_case（ADR-026）
- 响应使用 model_dump(mode="json") 序列化
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 请求 DTO（learning.md §10.2）
# ---------------------------------------------------------------------------


class RecomputeRequest(BaseModel):
    """重算 study_records 请求（learning.md §8.1）。

    所有字段可选：单用户/全量 + 时间范围限定。
    """

    user_id: str | None = None
    start_date: date | None = None
    end_date: date | None = None


# ---------------------------------------------------------------------------
# 响应 DTO（learning.md §10.1）
# ---------------------------------------------------------------------------


class DayStats(BaseModel):
    """单日统计（learning.md §2.2 today）。"""

    practice_count: int = 0
    question_count: int = 0
    attempt_count: int = 0
    recording_count: int = 0
    duration_seconds: int = 0


class StreakStats(BaseModel):
    """连续学习天数（learning.md §2.4 streak）。"""

    current_days: int
    longest_days: int


class CumulativeStats(BaseModel):
    """累计统计（learning.md §2.2 cumulative）。"""

    total_sessions: int
    total_questions: int
    total_attempts: int
    total_recordings: int
    total_duration_seconds: int


class GoalProgress(BaseModel):
    """目标达成度（learning.md §2.2 goal_progress，无 active goal 全 null）。"""

    daily_goal_minutes: int | None = None
    daily_completed_minutes: float | None = None
    weekly_goal_minutes: int | None = None
    weekly_completed_minutes: float | None = None


class LearningOverview(BaseModel):
    """学习概览（learning.md §2.2）。"""

    today: DayStats
    streak: StreakStats
    cumulative: CumulativeStats
    goal_progress: GoalProgress


class TrendPoint(BaseModel):
    """趋势点（learning.md §10.1，daily/weekly/monthly 共用）。

    daily 用 date；weekly 用 week_start + week_end；monthly 用 month。
    其余聚合字段共用。补零日期同样用本 DTO。
    """

    date: str | None = None
    week_start: str | None = None
    week_end: str | None = None
    month: str | None = None
    practice_count: int = 0
    question_count: int = 0
    attempt_count: int = 0
    recording_count: int = 0
    duration_seconds: int = 0


class TrendResponse(BaseModel):
    """趋势响应（learning.md §3.2/§4.2/§5.2）。"""

    granularity: Literal["daily", "weekly", "monthly"]
    timezone: str
    points: list[TrendPoint]


class TopicStat(BaseModel):
    """主题分布项（learning.md §6.2）。"""

    topic_id: str
    topic_name: str
    attempt_count: int
    duration_seconds: int


class TopicsDistributionResponse(BaseModel):
    """主题分布响应（learning.md §6.2）。"""

    range_months: int
    timezone: str
    topics: list[TopicStat]


class PartStat(BaseModel):
    """Part 分布项（learning.md §7.2）。"""

    part: int
    attempt_count: int
    duration_seconds: int


class PartsDistributionResponse(BaseModel):
    """Part 分布响应（learning.md §7.2）。"""

    range_months: int
    timezone: str
    parts: list[PartStat]


class RecomputeResponse(BaseModel):
    """重算响应（learning.md §8.2）。"""

    recomputed_users: int
    recomputed_records: int
    deleted_records: int
    duration_seconds_total: int


# 范围校验常量（learning.md §3.1/§4.1/§5.1/§6.1）
DAYS_MIN, DAYS_MAX = 1, 90
WEEKS_MIN, WEEKS_MAX = 1, 52
MONTHS_MIN, MONTHS_MAX = 1, 24


def validate_days(days: int) -> None:
    if not DAYS_MIN <= days <= DAYS_MAX:
        raise _range_error("days", days, DAYS_MIN, DAYS_MAX)


def validate_weeks(weeks: int) -> None:
    if not WEEKS_MIN <= weeks <= WEEKS_MAX:
        raise _range_error("weeks", weeks, WEEKS_MIN, WEEKS_MAX)


def validate_months(months: int) -> None:
    if not MONTHS_MIN <= months <= MONTHS_MAX:
        raise _range_error("months", months, MONTHS_MIN, MONTHS_MAX)


def _range_error(field: str, value: int, lo: int, hi: int) -> Exception:
    from app.core.exceptions import AppError  # noqa: PLC0415

    return AppError(
        code=1001,
        message="参数校验失败",
        http_status=422,
        details=[
            {
                "field": field,
                "message": f"{field}={value} 越界，合法范围 [{lo}, {hi}]",
            }
        ],
    )


__all__ = [
    "CumulativeStats",
    "DayStats",
    "DAYS_MAX",
    "DAYS_MIN",
    "GoalProgress",
    "LearningOverview",
    "MONTHS_MAX",
    "MONTHS_MIN",
    "PartStat",
    "PartsDistributionResponse",
    "RecomputeRequest",
    "RecomputeResponse",
    "StreakStats",
    "TopicStat",
    "TopicsDistributionResponse",
    "TrendPoint",
    "TrendResponse",
    "WEEKS_MAX",
    "WEEKS_MIN",
    "validate_days",
    "validate_months",
    "validate_weeks",
]
