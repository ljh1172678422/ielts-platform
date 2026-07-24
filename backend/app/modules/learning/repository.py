"""Learning 模块 SQLAlchemy 查询封装（system-architecture §3）。

对齐 learning.md §2-§8：
- overview：today/cumulative 从 study_records 读；streak 从 study_records 连续段；
  goal_progress 从 user_goals(active) 读目标 + study_records 读完成
- daily/weekly/monthly：study_records 按 record_date 切分，补零
- topics/parts：实时从事实表（attempts JOIN sq JOIN recordings）聚合，不查 study_records
- recompute：基于事实表 DELETE+INSERT study_records（ADR-008）

时区一致性（ADR-018）：所有按日/周/月切分基于 user_profiles.timezone。
duration 口径（ADR-016）：SUM(recordings.duration_seconds WHERE status='uploaded')。
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import StudyRecord, UserActivityLog
from app.models.practice import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionQuestion,
    Recording,
)
from app.models.user import User, UserGoal, UserProfile

# 状态常量（与 practice.md §2.2/§4.2/§6 对齐）
_RECORDING_UPLOADED = "uploaded"
_ATTEMPT_SUBMITTED = "submitted"
_SESSION_COMPLETED = "completed"
_GOAL_ACTIVE = "active"


# ---------------------------------------------------------------------------
# 时区工具（ADR-018）
# ---------------------------------------------------------------------------


def get_timezone(timezone_name: str | None) -> ZoneInfo:
    """解析时区名，无效回退 Asia/Shanghai（ADR-018）。"""
    try:
        return ZoneInfo(timezone_name or "Asia/Shanghai")
    except (KeyError, ValueError):
        return ZoneInfo("Asia/Shanghai")


async def get_user_timezone(db: AsyncSession, user_id: int) -> str:
    """查 user_profiles.timezone（默认 Asia/Shanghai）。"""
    stmt = select(UserProfile.timezone).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    tz = result.scalar_one_or_none()
    return tz or "Asia/Shanghai"


def to_local_date(utc_dt: datetime, tz: ZoneInfo) -> date:
    """UTC 时间按用户时区转本地 date。"""
    return utc_dt.astimezone(tz).date()


def today_in_timezone(tz: ZoneInfo) -> date:
    """按用户时区算今日 date。"""
    return datetime.now(UTC).astimezone(tz).date()


# ---------------------------------------------------------------------------
# overview：today + streak + cumulative + goal_progress（learning.md §2.4）
# ---------------------------------------------------------------------------


async def get_study_record_for_date(
    db: AsyncSession, user_id: int, record_date: date
) -> StudyRecord | None:
    """查指定日的 study_record（learning.md §2.4 step 2 today）。"""
    stmt = select(StudyRecord).where(
        StudyRecord.user_id == user_id,
        StudyRecord.record_date == record_date,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_cumulative_stats(
    db: AsyncSession, user_id: int
) -> dict[str, int]:
    """SUM 聚合 study_records 全部记录（learning.md §2.4 step 4 cumulative）。

    total_sessions = SUM(practice_count)（完成的会话数）
    total_questions = SUM(question_count)
    total_attempts = SUM(attempt_count)
    total_recordings = SUM(recording_count)
    total_duration_seconds = SUM(duration_seconds)
    """
    stmt = select(
        func.coalesce(func.sum(StudyRecord.practice_count), 0).label("total_sessions"),
        func.coalesce(func.sum(StudyRecord.question_count), 0).label("total_questions"),
        func.coalesce(func.sum(StudyRecord.attempt_count), 0).label("total_attempts"),
        func.coalesce(func.sum(StudyRecord.recording_count), 0).label("total_recordings"),
        func.coalesce(func.sum(StudyRecord.duration_seconds), 0).label("total_duration"),
    ).where(StudyRecord.user_id == user_id)
    result = await db.execute(stmt)
    row = result.one()
    return {
        "total_sessions": int(row.total_sessions or 0),
        "total_questions": int(row.total_questions or 0),
        "total_attempts": int(row.total_attempts or 0),
        "total_recordings": int(row.total_recordings or 0),
        "total_duration_seconds": int(row.total_duration or 0),
    }


async def get_all_record_dates(
    db: AsyncSession, user_id: int
) -> list[date]:
    """查该用户全部有 study_record 的 record_date（learning.md §2.4 step 3 streak）。

    ASC 排序，service 层在内存中计算 current_days/longest_days。
    """
    stmt = (
        select(StudyRecord.record_date)
        .where(StudyRecord.user_id == user_id)
        .order_by(StudyRecord.record_date.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_active_goal(
    db: AsyncSession, user_id: int
) -> UserGoal | None:
    """查 active user_goal（learning.md §2.4 step 5）。"""
    stmt = select(UserGoal).where(
        UserGoal.user_id == user_id,
        UserGoal.status == _GOAL_ACTIVE,
        UserGoal.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def sum_study_records_for_dates(
    db: AsyncSession, user_id: int, dates: list[date]
) -> dict[str, int]:
    """聚合指定日期范围的 study_records（learning.md §2.4 step 5 goal_progress）。

    返回 {duration_seconds, ...}，goal_progress 只需要 duration_seconds。
    """
    if not dates:
        return {"duration_seconds": 0}
    stmt = select(
        func.coalesce(func.sum(StudyRecord.duration_seconds), 0).label("duration"),
    ).where(
        StudyRecord.user_id == user_id,
        StudyRecord.record_date.in_(dates),
    )
    result = await db.execute(stmt)
    return {"duration_seconds": int(result.scalar_one() or 0)}


# ---------------------------------------------------------------------------
# daily/weekly/monthly 趋势（learning.md §3/§4/§5）
# ---------------------------------------------------------------------------


async def get_study_records_in_range(
    db: AsyncSession, user_id: int, start: date, end: date
) -> list[StudyRecord]:
    """查 [start, end] 范围的 study_records（learning.md §3.4/§4.4/§5.4）。"""
    stmt = (
        select(StudyRecord)
        .where(
            StudyRecord.user_id == user_id,
            StudyRecord.record_date >= start,
            StudyRecord.record_date <= end,
        )
        .order_by(StudyRecord.record_date.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# topics/parts 分布（learning.md §6/§7，实时从事实表聚合）
# ---------------------------------------------------------------------------


async def get_topics_distribution(
    db: AsyncSession, user_id: int, start_utc: datetime, end_utc: datetime
) -> list[dict[str, Any]]:
    """主题分布：实时从事实表聚合（learning.md §6.4）。

    - attempts.status='submitted' AND submitted_at ∈ [start_utc, end_utc]
    - JOIN sq 取 question_snapshot.topic_id/topic_name
    - LEFT JOIN recordings(status='uploaded') 取 duration（ADR-016）
    - GROUP BY topic_id, topic_name，COUNT(attempt) / SUM(duration)
    """
    # snapshot 是 JSONB，用 ->> 取 key（PostgreSQL JSON 操作符）
    topic_id_expr = PracticeSessionQuestion.question_snapshot["topic_id"].as_string()
    # topic_name 在 snapshot 里可能没有（旧数据兼容），用 COALESCE 兜底 "Other"
    topic_name_expr = func.coalesce(
        PracticeSessionQuestion.question_snapshot["topic_name"].as_string(),
        "Other",
    )

    stmt = (
        select(
            topic_id_expr.label("topic_id"),
            topic_name_expr.label("topic_name"),
            func.count(PracticeAttempt.id).label("attempt_count"),
            func.coalesce(
                func.sum(Recording.duration_seconds), 0
            ).label("duration_seconds"),
        )
        .select_from(PracticeAttempt)
        .join(
            PracticeSessionQuestion,
            PracticeSessionQuestion.id == PracticeAttempt.session_question_id,
        )
        .outerjoin(
            Recording,
            (Recording.attempt_id == PracticeAttempt.id)
            & (Recording.status == _RECORDING_UPLOADED),
        )
        .where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.status == _ATTEMPT_SUBMITTED,
            PracticeAttempt.submitted_at >= start_utc,
            PracticeAttempt.submitted_at < end_utc,
        )
        .group_by(topic_id_expr, topic_name_expr)
        .order_by(func.count(PracticeAttempt.id).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "topic_id": str(row.topic_id) if row.topic_id is not None else "0",
            "topic_name": row.topic_name or "Other",
            "attempt_count": int(row.attempt_count or 0),
            "duration_seconds": int(row.duration_seconds or 0),
        }
        for row in rows
    ]


async def get_parts_distribution(
    db: AsyncSession, user_id: int, start_utc: datetime, end_utc: datetime
) -> list[dict[str, Any]]:
    """Part 分布：实时从事实表聚合（learning.md §7.3）。

    同 topics，GROUP BY question_snapshot.part。
    """
    part_expr = PracticeSessionQuestion.question_snapshot["part"].as_integer()

    stmt = (
        select(
            part_expr.label("part"),
            func.count(PracticeAttempt.id).label("attempt_count"),
            func.coalesce(
                func.sum(Recording.duration_seconds), 0
            ).label("duration_seconds"),
        )
        .select_from(PracticeAttempt)
        .join(
            PracticeSessionQuestion,
            PracticeSessionQuestion.id == PracticeAttempt.session_question_id,
        )
        .outerjoin(
            Recording,
            (Recording.attempt_id == PracticeAttempt.id)
            & (Recording.status == _RECORDING_UPLOADED),
        )
        .where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.status == _ATTEMPT_SUBMITTED,
            PracticeAttempt.submitted_at >= start_utc,
            PracticeAttempt.submitted_at < end_utc,
        )
        .group_by(part_expr)
        .order_by(part_expr.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "part": int(row.part) if row.part is not None else 0,
            "attempt_count": int(row.attempt_count or 0),
            "duration_seconds": int(row.duration_seconds or 0),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# recompute（learning.md §8.4，ADR-008，事务内 DELETE+INSERT）
# ---------------------------------------------------------------------------


async def user_exists(db: AsyncSession, user_id: int) -> bool:
    """校验 user_id 指定用户存在（learning.md §8.3 7001）。"""
    stmt = select(func.count()).select_from(User).where(
        User.id == user_id,
        User.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return int(result.scalar_one()) > 0


async def list_user_ids(db: AsyncSession) -> list[int]:
    """全量重算时枚举所有用户 id（learning.md §8.4 step 2）。"""
    stmt = select(User.id).where(User.deleted_at.is_(None)).order_by(User.id.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def recompute_for_user(
    db: AsyncSession,
    user_id: int,
    *,
    timezone_name: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, int]:
    """重算单用户 study_records（learning.md §8.4 step 3）。

    返回 {recomputed_records, deleted_records, duration_seconds_total}。
    在调用方事务内执行：DELETE 该用户范围内旧记录 → INSERT 新聚合记录。
    """
    tz = get_timezone(timezone_name)

    # 查事实表：submitted attempts + recording duration + sq（含 sq_id 用于 question_count）
    # 一次查询拿全：attempt.submitted_at / attempt.id / sq.id / recording.duration_seconds
    stmt = (
        select(
            PracticeAttempt.id.label("attempt_id"),
            PracticeAttempt.submitted_at.label("submitted_at"),
            PracticeAttempt.session_question_id.label("sq_id"),
            Recording.duration_seconds.label("duration_seconds"),
        )
        .select_from(PracticeAttempt)
        .outerjoin(
            Recording,
            (Recording.attempt_id == PracticeAttempt.id)
            & (Recording.status == _RECORDING_UPLOADED),
        )
        .where(
            PracticeAttempt.user_id == user_id,
            PracticeAttempt.status == _ATTEMPT_SUBMITTED,
            PracticeAttempt.submitted_at.is_not(None),
        )
    )
    # completed sessions 用于 practice_count（按 completed_at 切日）
    sess_stmt = select(PracticeSession.completed_at).where(
        PracticeSession.user_id == user_id,
        PracticeSession.status == _SESSION_COMPLETED,
        PracticeSession.completed_at.is_not(None),
    )

    result = await db.execute(stmt)
    attempts = result.all()
    sess_result = await db.execute(sess_stmt)
    sessions = sess_result.all()

    # 按用户时区切日聚合（ADR-018）
    # 日级聚合：record_date → 聚合桶（含 _seen_sqs 内部集合用于 distinct sq 计数）
    daily: dict[date, dict[str, Any]] = {}

    def _bucket(d: date) -> dict[str, Any]:
        return daily.setdefault(
            d,
            {
                "practice_count": 0,
                "question_count": 0,
                "attempt_count": 0,
                "recording_count": 0,
                "duration_seconds": 0,
                "_seen_sqs": set(),
            },
        )

    def _in_range(local_d: date) -> bool:
        if start_date and local_d < start_date:
            return False
        if end_date and local_d > end_date:
            return False
        return True

    # attempts → attempt_count / question_count / recording_count / duration_seconds
    for row in attempts:
        local_d = to_local_date(row.submitted_at, tz)
        if not _in_range(local_d):
            continue
        b = _bucket(local_d)
        b["attempt_count"] += 1
        # question_count = COUNT(DISTINCT sq)（已答题的 sq 数）
        if row.sq_id is not None and row.sq_id not in b["_seen_sqs"]:
            b["_seen_sqs"].add(row.sq_id)
            b["question_count"] += 1
        if row.duration_seconds is not None:
            b["recording_count"] += 1
            b["duration_seconds"] += int(row.duration_seconds)

    # sessions → practice_count（按 completed_at 切日）
    for row in sessions:
        local_d = to_local_date(row.completed_at, tz)
        if not _in_range(local_d):
            continue
        _bucket(local_d)["practice_count"] += 1

    # 范围内 DELETE 旧记录
    del_stmt = delete(StudyRecord).where(StudyRecord.user_id == user_id)
    if start_date is not None:
        del_stmt = del_stmt.where(StudyRecord.record_date >= start_date)
    if end_date is not None:
        del_stmt = del_stmt.where(StudyRecord.record_date <= end_date)
    del_result = await db.execute(del_stmt)
    deleted = int(del_result.rowcount or 0)

    # INSERT 新聚合记录
    duration_total = 0
    inserted = 0
    if daily:
        rows = [
            {
                "user_id": user_id,
                "record_date": d,
                "practice_count": b["practice_count"],
                "question_count": b["question_count"],
                "attempt_count": b["attempt_count"],
                "recording_count": b["recording_count"],
                "duration_seconds": b["duration_seconds"],
            }
            for d, b in daily.items()
        ]
        await db.execute(pg_insert(StudyRecord), rows)
        inserted = len(rows)
        duration_total = sum(b["duration_seconds"] for b in daily.values())

    return {
        "recomputed_records": inserted,
        "deleted_records": deleted,
        "duration_seconds_total": duration_total,
    }


# ---------------------------------------------------------------------------
# activity_log（learning.md §9.5）
# ---------------------------------------------------------------------------


def build_recompute_log(
    *,
    admin_id: int,
    target_user_id: int,
    recomputed_records: int,
    deleted_records: int,
) -> UserActivityLog:
    """构造 recompute 活动日志（learning.md §9.5）。"""
    return UserActivityLog(
        user_id=admin_id,
        action="study_records_recomputed",
        entity_type="user",
        entity_id=target_user_id,
        metadata_={
            "recomputed_records": recomputed_records,
            "deleted_records": deleted_records,
        },
    )


# ---------------------------------------------------------------------------
# 范围计算工具
# ---------------------------------------------------------------------------


def week_monday(d: date) -> date:
    """返回 d 所在周的周一日期（ISO 8601，learning.md §4.1）。"""
    return d - timedelta(days=d.weekday())


def add_months(d: date, months: int) -> date:
    """日期加 N 月（保留日，超出月末则截到月末，learning.md §5.1）。"""
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    # 月末截断
    import calendar  # noqa: PLC0415

    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last_day))


def month_start(d: date) -> date:
    """返回 d 所在月的 1 号（learning.md §5.1）。"""
    return date(d.year, d.month, 1)
