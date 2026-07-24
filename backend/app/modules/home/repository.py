"""Home 模块 SQLAlchemy 查询封装（system-architecture §3）。

对齐 home.md §2.6：
- today/streak/goal_progress：复用 learning.repository 的子查询（直接 import 复用）
- recent_practice：未完成 session（ORDER BY updated_at DESC LIMIT 1）+ completed_questions 统计
- recommendations 5 级短路（ADR-028）：
  level 1: unfinished_session → sq JOIN speaking_questions(published)
  level 2: recent_topic → 近 7 天 attempts JOIN sq.snapshot.topic_id 去重 → 该 topic 题目
  level 3: favorite → favorites LEFT JOIN practice_attempts(submitted) → 无 submitted 的
  level 4: less_practiced_part → GROUP BY snapshot.part → ORDER BY COUNT ASC → 该 part 题目
  level 5: popular → ORDER BY practice_count DESC（兜底）
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite import Favorite
from app.models.practice import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionQuestion,
)
from app.models.question import SpeakingQuestion, SpeakingTopic
from app.modules.learning.repository import (
    get_active_goal,
    get_all_record_dates,
    get_study_record_for_date,
    get_timezone,
    get_user_timezone,
    today_in_timezone,
    week_monday,
)

# 状态常量（与 practice.md 对齐）
_SESSION_ACTIVE = {"created", "in_progress"}
_ATTEMPT_SUBMITTED = "submitted"
_PUBLISHED = "published"


# ---------------------------------------------------------------------------
# 复用 learning.repository（home.md §5 复用 learning.md §2）
# ---------------------------------------------------------------------------


# 直接再导出，方便 service 层单点引用
__all__ = [
    "fetch_today_streak_goal",
    "get_unfinished_session",
    "count_completed_questions",
    "get_unfinished_session_questions",
    "get_recent_topic_questions",
    "get_favorite_questions",
    "get_less_practiced_part_questions",
    "get_popular_questions",
    "build_topic_ref",
    "build_recommendation",
    "to_recommendation_dict",
]


async def fetch_today_streak_goal(
    db: AsyncSession, user_id: int
) -> dict[str, Any]:
    """聚合 today + streak + goal_progress（home.md §2.6 step 2）。

    复用 learning.repository 的子查询。goal_progress 含 target_score/exam_date
    （home.md §4 扩展）。
    """
    tz_name = await get_user_timezone(db, user_id)
    tz = get_timezone(tz_name)
    today = today_in_timezone(tz)

    # today
    today_rec = await get_study_record_for_date(db, user_id, today)
    if today_rec is not None:
        today_stats = {
            "practice_count": today_rec.practice_count,
            "question_count": today_rec.question_count,
            "attempt_count": today_rec.attempt_count,
            "recording_count": today_rec.recording_count,
            "duration_seconds": today_rec.duration_seconds,
        }
        today_duration = today_rec.duration_seconds
    else:
        today_stats = {
            "practice_count": 0,
            "question_count": 0,
            "attempt_count": 0,
            "recording_count": 0,
            "duration_seconds": 0,
        }
        today_duration = 0

    # streak
    all_dates = await get_all_record_dates(db, user_id)
    current_days, longest_days = _compute_streak(all_dates, today)

    # goal_progress（home.md §4 扩展 target_score/exam_date）
    goal = await get_active_goal(db, user_id)
    if goal is None:
        goal_progress = None
    else:
        # 本周 duration
        monday = week_monday(today)
        week_dates = [
            monday + timedelta(days=i) for i in range((today - monday).days + 1)
        ]
        from app.modules.learning.repository import (
            sum_study_records_for_dates,
        )  # noqa: PLC0415

        week_agg = await sum_study_records_for_dates(db, user_id, week_dates)
        week_duration = week_agg["duration_seconds"]

        daily_goal = goal.daily_goal_minutes
        weekly_goal = goal.weekly_goal_minutes
        goal_progress = {
            "daily_goal_minutes": daily_goal,
            "daily_completed_minutes": (
                round(today_duration / 60.0, 1) if daily_goal is not None else None
            ),
            "weekly_goal_minutes": weekly_goal,
            "weekly_completed_minutes": (
                round(week_duration / 60.0, 1) if weekly_goal is not None else None
            ),
            "target_score": (
                float(goal.target_score) if goal.target_score is not None else None
            ),
            "exam_date": goal.exam_date,
        }

    return {
        "today": today_stats,
        "streak": {"current_days": current_days, "longest_days": longest_days},
        "goal_progress": goal_progress,
    }


def _compute_streak(all_dates: list[date], today: date) -> tuple[int, int]:
    """streak 算法（与 learning.service._compute_streak 一致，本地复制避免循环依赖）。"""
    if not all_dates:
        return 0, 0
    date_set = set(all_dates)
    current_days = 0
    if today in date_set:
        d = today
        while d in date_set:
            current_days += 1
            d -= timedelta(days=1)
    sorted_dates = sorted(date_set)
    longest = 1
    cur = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] + timedelta(days=1):
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    return current_days, longest


# ---------------------------------------------------------------------------
# recent_practice（home.md §2.6 step 2）
# ---------------------------------------------------------------------------


async def get_unfinished_session(
    db: AsyncSession, user_id: int
) -> PracticeSession | None:
    """查最近一个未完成 session（ORDER BY updated_at DESC LIMIT 1）。"""
    stmt = (
        select(PracticeSession)
        .where(
            PracticeSession.user_id == user_id,
            PracticeSession.status.in_(_SESSION_ACTIVE),
        )
        .order_by(PracticeSession.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def count_completed_questions(
    db: AsyncSession, session_id: int
) -> int:
    """统计 session 中已有 submitted/skipped attempt 的 sq 数（home.md §2.3）。"""
    # 对每个 sq 检查是否存在 submitted/skipped attempt → COUNT(DISTINCT sq_id)
    stmt = (
        select(func.count(func.distinct(PracticeAttempt.session_question_id)))
        .where(
            PracticeAttempt.session_question_id.in_(
                select(PracticeSessionQuestion.id).where(
                    PracticeSessionQuestion.session_id == session_id
                )
            ),
            PracticeAttempt.status.in_(("submitted", "skipped")),
        )
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


# ---------------------------------------------------------------------------
# 推荐算法 level 1: unfinished_session（home.md §2.5）
# ---------------------------------------------------------------------------


async def get_unfinished_session_questions(
    db: AsyncSession,
    session_id: int,
    *,
    exclude_ids: set[int],
    limit: int,
) -> list[SpeakingQuestion]:
    """level 1：未完成 session 的题目（按 sq.sort_order，home.md §2.5 level 1）。

    仅返回该 session 的 sq 对应的 published 题目；排除已取的 question_id。
    """
    if limit <= 0:
        return []
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic))
        .join(
            PracticeSessionQuestion,
            PracticeSessionQuestion.question_id == SpeakingQuestion.id,
        )
        .where(
            PracticeSessionQuestion.session_id == session_id,
            SpeakingQuestion.status == _PUBLISHED,
        )
        .order_by(PracticeSessionQuestion.sort_order.asc())
    )
    if exclude_ids:
        stmt = stmt.where(SpeakingQuestion.id.notin_(exclude_ids))
    # 不在 SQL 层 LIMIT（需要排除后取 N），在 Python 层过滤更简单
    result = await db.execute(stmt)
    items: list[SpeakingQuestion] = []
    for q in result.scalars().unique():
        if q.id in exclude_ids:
            continue
        items.append(q)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# 推荐算法 level 2: recent_topic（home.md §2.5）
# ---------------------------------------------------------------------------


async def get_recent_topic_questions(
    db: AsyncSession,
    user_id: int,
    *,
    exclude_ids: set[int],
    limit: int,
) -> list[SpeakingQuestion]:
    """level 2：近 7 天练习过的主题下的题目（home.md §2.5 level 2）。

    - 近 7 天 attempts → JOIN sq.snapshot.topic_id → 去重 topic_id 列表
    - 查这些 topic 下的 published 题目，排除 exclude_ids
    - 按 created_at DESC
    """
    if limit <= 0:
        return []
    since = datetime.now(UTC) - timedelta(days=7)
    topic_id_expr = PracticeSessionQuestion.question_snapshot["topic_id"].as_string()

    # 1. 取近 7 天 attempts 涉及的 topic_id（去重）
    topic_stmt = (
        select(func.distinct(topic_id_expr))
        .select_from(PracticeAttempt)
        .join(
            PracticeSessionQuestion,
            PracticeSessionQuestion.id == PracticeAttempt.session_question_id,
        )
        .where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.created_at >= since,
        )
    )
    topic_result = await db.execute(topic_stmt)
    topic_ids_str = [r for r in topic_result.scalars().all() if r is not None]
    topic_ids: list[int] = []
    for s in topic_ids_str:
        try:
            topic_ids.append(int(s))
        except (TypeError, ValueError):
            continue
    if not topic_ids:
        return []

    # 2. 查这些 topic 下的 published 题目（排除已取），按 created_at DESC
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic))
        .where(
            SpeakingQuestion.topic_id.in_(topic_ids),
            SpeakingQuestion.status == _PUBLISHED,
        )
        .order_by(SpeakingQuestion.created_at.desc())
    )
    if exclude_ids:
        stmt = stmt.where(SpeakingQuestion.id.notin_(exclude_ids))
    result = await db.execute(stmt)
    items: list[SpeakingQuestion] = []
    for q in result.scalars().unique():
        if q.id in exclude_ids:
            continue
        items.append(q)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# 推荐算法 level 3: favorite（home.md §2.5）
# ---------------------------------------------------------------------------


async def get_favorite_questions(
    db: AsyncSession,
    user_id: int,
    *,
    exclude_ids: set[int],
    limit: int,
) -> list[SpeakingQuestion]:
    """level 3：收藏题目中未练习过的（home.md §2.5 level 3）。

    - favorites → LEFT JOIN practice_attempts(submitted) → 取无 submitted 的
    - JOIN speaking_questions(published)
    - 按 favorites.created_at DESC（最近收藏优先）
    """
    if limit <= 0:
        return []

    # 子查询：用户已 submitted 的 question_id 集合（通过 sq 反查 question_id）
    submitted_qids_subq = (
        select(PracticeSessionQuestion.question_id)
        .join(
            PracticeAttempt,
            PracticeAttempt.session_question_id == PracticeSessionQuestion.id,
        )
        .where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.status == _ATTEMPT_SUBMITTED,
        )
    ).subquery()

    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic))
        .join(Favorite, Favorite.question_id == SpeakingQuestion.id)
        .where(
            Favorite.user_id == user_id,
            SpeakingQuestion.status == _PUBLISHED,
            SpeakingQuestion.id.notin_(select(submitted_qids_subq.c.question_id)),
        )
        .order_by(Favorite.created_at.desc())
    )
    if exclude_ids:
        stmt = stmt.where(SpeakingQuestion.id.notin_(exclude_ids))
    result = await db.execute(stmt)
    items: list[SpeakingQuestion] = []
    for q in result.scalars().unique():
        if q.id in exclude_ids:
            continue
        items.append(q)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# 推荐算法 level 4: less_practiced_part（home.md §2.5）
# ---------------------------------------------------------------------------


async def get_less_practiced_part_questions(
    db: AsyncSession,
    user_id: int,
    *,
    exclude_ids: set[int],
    limit: int,
) -> list[SpeakingQuestion]:
    """level 4：用户最少练习的 Part 下的题目（home.md §2.5 level 4）。

    - GROUP BY snapshot.part → COUNT(attempts) → ORDER BY COUNT ASC → LIMIT 1
    - 查该 part 下的 published 题目，排除已取
    - 按 created_at DESC
    """
    if limit <= 0:
        return []
    part_expr = PracticeSessionQuestion.question_snapshot["part"].as_integer()

    # 1. 找用户练习次数最少的 part
    part_stmt = (
        select(
            part_expr.label("part"),
            func.count(PracticeAttempt.id).label("cnt"),
        )
        .select_from(PracticeAttempt)
        .join(
            PracticeSessionQuestion,
            PracticeSessionQuestion.id == PracticeAttempt.session_question_id,
        )
        .where(PracticeAttempt.user_id == user_id)
        .group_by(part_expr)
        .order_by(func.count(PracticeAttempt.id).asc())
        .limit(1)
    )
    part_result = await db.execute(part_stmt)
    part_row = part_result.first()
    if part_row is None or part_row.part is None:
        return []
    least_part = int(part_row.part)

    # 2. 查该 part 下的 published 题目（排除已取），按 created_at DESC
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic))
        .where(
            SpeakingQuestion.part == least_part,
            SpeakingQuestion.status == _PUBLISHED,
        )
        .order_by(SpeakingQuestion.created_at.desc())
    )
    if exclude_ids:
        stmt = stmt.where(SpeakingQuestion.id.notin_(exclude_ids))
    result = await db.execute(stmt)
    items: list[SpeakingQuestion] = []
    for q in result.scalars().unique():
        if q.id in exclude_ids:
            continue
        items.append(q)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# 推荐算法 level 5: popular（home.md §2.5，兜底）
# ---------------------------------------------------------------------------


async def get_popular_questions(
    db: AsyncSession,
    *,
    exclude_ids: set[int],
    limit: int,
) -> list[SpeakingQuestion]:
    """level 5：全题库 published，按 practice_count DESC（home.md §2.5 level 5）。

    practice_count = 该题被多少 session 引用（COUNT(session_questions)）。
    """
    if limit <= 0:
        return []
    practice_count_expr = (
        select(func.count())
        .select_from(PracticeSessionQuestion)
        .where(PracticeSessionQuestion.question_id == SpeakingQuestion.id)
        .scalar_subquery()
    )
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic))
        .where(SpeakingQuestion.status == _PUBLISHED)
        .order_by(
            func.coalesce(practice_count_expr, 0).desc(),
            SpeakingQuestion.created_at.desc(),
        )
    )
    if exclude_ids:
        stmt = stmt.where(SpeakingQuestion.id.notin_(exclude_ids))
    result = await db.execute(stmt)
    items: list[SpeakingQuestion] = []
    for q in result.scalars().unique():
        if q.id in exclude_ids:
            continue
        items.append(q)
        if len(items) >= limit:
            break
    return items


# ---------------------------------------------------------------------------
# practice_count 批量查询（推荐项需要展示 practice_count）
# ---------------------------------------------------------------------------


async def batch_practice_counts_by_questions(
    db: AsyncSession, question_ids: list[int]
) -> dict[int, int]:
    """批量查询题目的 practice_count（COUNT(session_questions)）。"""
    if not question_ids:
        return {}
    stmt = (
        select(
            PracticeSessionQuestion.question_id.label("qid"),
            func.count().label("cnt"),
        )
        .where(PracticeSessionQuestion.question_id.in_(question_ids))
        .group_by(PracticeSessionQuestion.question_id)
    )
    result = await db.execute(stmt)
    return {int(row.qid): int(row.cnt or 0) for row in result.all()}


# ---------------------------------------------------------------------------
# DTO 组装工具
# ---------------------------------------------------------------------------


def build_topic_ref(topic: SpeakingTopic) -> dict[str, Any]:
    """构造 TopicRef dict。"""
    return {"id": str(topic.id), "name": topic.name}


def build_recommendation(
    question: SpeakingQuestion,
    *,
    reason: str,
    practice_count: int,
) -> dict[str, Any]:
    """构造 Recommendation dict（home.md §4）。"""
    return {
        "id": str(question.id),
        "part": question.part,
        "title": question.title,
        "topic": build_topic_ref(question.topic) if question.topic is not None else {"id": "0", "name": "Other"},
        "difficulty": question.difficulty,
        "practice_count": practice_count,
        "reason": reason,
    }


def to_recommendation_dict(
    questions: list[SpeakingQuestion],
    *,
    reason: str,
    practice_counts: dict[int, int],
) -> list[dict[str, Any]]:
    """批量构造 Recommendation dict（附带 practice_count）。"""
    return [
        build_recommendation(
            q, reason=reason, practice_count=practice_counts.get(q.id, 0)
        )
        for q in questions
    ]
