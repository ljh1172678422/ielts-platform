"""Home 模块 Pydantic schemas（对齐 home.md §4 DTO 速查）。

- HomeGoalProgress 扩展 learning GoalProgress + target_score/exam_date
- Recommendation = QuestionListItem - is_favorited + reason
- 全部 snake_case（ADR-026）；id 序列化为 str（ADR-025）
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

# 推荐来源（home.md §2.5，ADR-028 5 级）
RecommendationReason = Literal[
    "unfinished_session",
    "recent_topic",
    "favorite",
    "less_practiced_part",
    "popular",
]


class DayStats(BaseModel):
    """单日统计（复用 learning.md §2.2）。"""

    practice_count: int = 0
    question_count: int = 0
    attempt_count: int = 0
    recording_count: int = 0
    duration_seconds: int = 0


class StreakStats(BaseModel):
    """连续学习天数（复用 learning.md §2.2）。"""

    current_days: int
    longest_days: int


class HomeGoalProgress(BaseModel):
    """active goal 进度（home.md §4，扩展 learning GoalProgress）。

    无 active goal 时由 service 层返回 None（whole field null）。
    """

    daily_goal_minutes: int | None = None
    daily_completed_minutes: float | None = None
    weekly_goal_minutes: int | None = None
    weekly_completed_minutes: float | None = None
    target_score: float | None = None
    exam_date: date | None = None


class UnfinishedSessionSummary(BaseModel):
    """未完成 session 摘要（home.md §4）。"""

    id: str
    status: str
    mode: str
    question_count: int
    completed_questions: int
    updated_at: str  # ISODateTime


class RecentPractice(BaseModel):
    """最近练习（home.md §4）。"""

    has_unfinished: bool
    session: UnfinishedSessionSummary | None = None


class TopicRef(BaseModel):
    """主题引用（复用 questions.md §2.2）。"""

    id: str
    name: str


class Recommendation(BaseModel):
    """推荐题目（home.md §4，QuestionListItem - is_favorited + reason）。

    不含 content/cue_card/source_*（列表语义，详情走 questions.md §3）。
    """

    id: str
    part: int
    title: str
    topic: TopicRef
    difficulty: int | None = None
    practice_count: int = 0
    reason: RecommendationReason


class HomeOverview(BaseModel):
    """首页聚合（home.md §4）。"""

    today: DayStats
    streak: StreakStats
    goal_progress: HomeGoalProgress | None
    recent_practice: RecentPractice
    recommendations: list[Recommendation]


__all__ = [
    "DayStats",
    "HomeGoalProgress",
    "HomeOverview",
    "Recommendation",
    "RecommendationReason",
    "RecentPractice",
    "StreakStats",
    "TopicRef",
    "UnfinishedSessionSummary",
]
