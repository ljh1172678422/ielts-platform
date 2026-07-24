"""Learning 模块业务逻辑（system-architecture §3：service 层）。

对齐 learning.md §2-§8：
- overview：today/streak/cumulative/goal_progress（ADR-018 时区切日）
- daily/weekly/monthly：补零 + timezone 切日
- topics/parts：实时从事实表聚合（ADR-016 duration 口径）
- recompute：admin 鉴权(2003) + user_id 校验(7001) + 事务(DELETE+INSERT)
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.user import User
from app.modules.learning import repository as repo
from app.modules.learning.schemas import (
    CumulativeStats,
    DayStats,
    GoalProgress,
    LearningOverview,
    PartsDistributionResponse,
    PartStat,
    RecomputeRequest,
    RecomputeResponse,
    StreakStats,
    TopicsDistributionResponse,
    TopicStat,
    TrendPoint,
    TrendResponse,
)

# 补零桶的字段顺序（learning.md §3.2）
_ZERO_FIELDS = {
    "practice_count": 0,
    "question_count": 0,
    "attempt_count": 0,
    "recording_count": 0,
    "duration_seconds": 0,
}


def _record_to_bucket(rec: Any) -> dict[str, int]:
    """study_record ORM → 聚合桶（learning.md §3.2 points）。"""
    return {
        "practice_count": rec.practice_count,
        "question_count": rec.question_count,
        "attempt_count": rec.attempt_count,
        "recording_count": rec.recording_count,
        "duration_seconds": rec.duration_seconds,
    }


def _zero_bucket() -> dict[str, int]:
    return dict(_ZERO_FIELDS)


# ---------------------------------------------------------------------------
# overview（learning.md §2）
# ---------------------------------------------------------------------------


async def get_overview(
    db: AsyncSession, *, current_user: User
) -> dict[str, Any]:
    """学习概览（learning.md §2.4）。

    1. 取 timezone
    2. today：study_records WHERE record_date = today_in_timezone
    3. streak：查全部 record_dates 内存计算 current_days / longest_days
    4. cumulative：SUM study_records 全部
    5. goal_progress：active user_goals + 本周 study_records duration
    """
    tz_name = await repo.get_user_timezone(db, current_user.id)
    tz = repo.get_timezone(tz_name)
    today = repo.today_in_timezone(tz)

    # today
    today_rec = await repo.get_study_record_for_date(db, current_user.id, today)
    if today_rec is not None:
        today_stats = DayStats(
            practice_count=today_rec.practice_count,
            question_count=today_rec.question_count,
            attempt_count=today_rec.attempt_count,
            recording_count=today_rec.recording_count,
            duration_seconds=today_rec.duration_seconds,
        )
    else:
        today_stats = DayStats()

    # streak
    all_dates = await repo.get_all_record_dates(db, current_user.id)
    current_days, longest_days = _compute_streak(all_dates, today)
    streak = StreakStats(current_days=current_days, longest_days=longest_days)

    # cumulative
    cum = await repo.get_cumulative_stats(db, current_user.id)
    cumulative = CumulativeStats(**cum)

    # goal_progress
    goal = await repo.get_active_goal(db, current_user.id)
    if goal is None:
        goal_progress = GoalProgress()
    else:
        # 今日 duration
        today_duration = (
            today_stats.duration_seconds if today_rec is not None else 0
        )
        # 本周 duration（周一到今日）
        monday = repo.week_monday(today)
        week_dates = [monday + timedelta(days=i) for i in range((today - monday).days + 1)]
        week_agg = await repo.sum_study_records_for_dates(db, current_user.id, week_dates)
        week_duration = week_agg["duration_seconds"]

        daily_goal = goal.daily_goal_minutes
        weekly_goal = goal.weekly_goal_minutes
        goal_progress = GoalProgress(
            daily_goal_minutes=daily_goal,
            daily_completed_minutes=round(today_duration / 60.0, 1) if daily_goal is not None else None,
            weekly_goal_minutes=weekly_goal,
            weekly_completed_minutes=round(week_duration / 60.0, 1) if weekly_goal is not None else None,
        )

    overview = LearningOverview(
        today=today_stats,
        streak=streak,
        cumulative=cumulative,
        goal_progress=goal_progress,
    )
    return overview.model_dump(mode="json")


def _compute_streak(
    all_dates: list[date], today: date
) -> tuple[int, int]:
    """streak 算法（learning.md §2.4 step 3）。

    - current_days：从今日（今日有数据）或昨日（今日无数据则从昨日）向前回溯连续天数
      * 今日有数据：从今日起算
      * 今日无数据：current_days = 0（MVP 简化，learning.md §2.4 注）
    - longest_days：最长连续段（全量内存计算）
    """
    if not all_dates:
        return 0, 0

    date_set = set(all_dates)

    # current_days
    current_days = 0
    if today in date_set:
        d = today
        while d in date_set:
            current_days += 1
            d -= timedelta(days=1)

    # longest_days：遍历排序后的 dates 找最长连续段
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
# daily（learning.md §3）
# ---------------------------------------------------------------------------


async def get_daily_trend(
    db: AsyncSession, *, current_user: User, days: int
) -> dict[str, Any]:
    """日趋势（learning.md §3.4）。

    1. 取 timezone
    2. 算今日 + N 天范围
    3. 查 study_records 在范围内
    4. 内存补零缺失日期
    5. 按 date ASC 返回
    """
    tz_name = await repo.get_user_timezone(db, current_user.id)
    tz = repo.get_timezone(tz_name)
    today = repo.today_in_timezone(tz)
    start = today - timedelta(days=days - 1)

    records = await repo.get_study_records_in_range(db, current_user.id, start, today)
    by_date = {r.record_date: _record_to_bucket(r) for r in records}

    points: list[TrendPoint] = []
    cur = start
    while cur <= today:
        b = by_date.get(cur) or _zero_bucket()
        points.append(
            TrendPoint(date=cur.isoformat(), **b)
        )
        cur += timedelta(days=1)

    resp = TrendResponse(granularity="daily", timezone=tz_name, points=points)
    return resp.model_dump(mode="json")


# ---------------------------------------------------------------------------
# weekly（learning.md §4）
# ---------------------------------------------------------------------------


async def get_weekly_trend(
    db: AsyncSession, *, current_user: User, weeks: int
) -> dict[str, Any]:
    """周趋势（learning.md §4.4）。

    1. 取 timezone，算本周一
    2. 范围：本周一-(weeks-1)*7 ~ 本周日
    3. 查 study_records
    4. 内存按周分组求和 + 补零
    5. 按 week_start ASC 返回
    """
    tz_name = await repo.get_user_timezone(db, current_user.id)
    tz = repo.get_timezone(tz_name)
    today = repo.today_in_timezone(tz)
    this_monday = repo.week_monday(today)
    start = this_monday - timedelta(days=(weeks - 1) * 7)
    end = this_monday + timedelta(days=6)

    records = await repo.get_study_records_in_range(db, current_user.id, start, end)
    by_week: dict[date, dict[str, int]] = {}
    for r in records:
        monday = repo.week_monday(r.record_date)
        b = by_week.setdefault(monday, _zero_bucket())
        for k in _ZERO_FIELDS:
            b[k] += getattr(r, k)

    points: list[TrendPoint] = []
    for i in range(weeks):
        ws = start + timedelta(days=i * 7)
        we = ws + timedelta(days=6)
        b = by_week.get(ws) or _zero_bucket()
        points.append(
            TrendPoint(
                week_start=ws.isoformat(),
                week_end=we.isoformat(),
                **b,
            )
        )

    resp = TrendResponse(granularity="weekly", timezone=tz_name, points=points)
    return resp.model_dump(mode="json")


# ---------------------------------------------------------------------------
# monthly（learning.md §5）
# ---------------------------------------------------------------------------


async def get_monthly_trend(
    db: AsyncSession, *, current_user: User, months: int
) -> dict[str, Any]:
    """月趋势（learning.md §5.4）。

    1. 取 timezone，算本月 1 号
    2. 范围：本月 1 号前 N-1 月 ~ 月末
    3. 查 study_records
    4. 内存按月分组求和 + 补零
    5. 按 month ASC 返回
    """
    tz_name = await repo.get_user_timezone(db, current_user.id)
    tz = repo.get_timezone(tz_name)
    today = repo.today_in_timezone(tz)
    this_month_start = repo.month_start(today)
    start = repo.add_months(this_month_start, -(months - 1))
    # end 取本月末
    next_month_start = repo.add_months(this_month_start, 1)
    end = next_month_start - timedelta(days=1)

    records = await repo.get_study_records_in_range(db, current_user.id, start, end)
    by_month: dict[str, dict[str, int]] = {}
    for r in records:
        key = f"{r.record_date.year:04d}-{r.record_date.month:02d}"
        b = by_month.setdefault(key, _zero_bucket())
        for k in _ZERO_FIELDS:
            b[k] += getattr(r, k)

    points: list[TrendPoint] = []
    for i in range(months):
        ms = repo.add_months(this_month_start, -i)
        # 倒序生成后排序，确保 ASC
        key = f"{ms.year:04d}-{ms.month:02d}"
        b = by_month.get(key) or _zero_bucket()
        points.append(TrendPoint(month=key, **b))
    points.reverse()

    resp = TrendResponse(granularity="monthly", timezone=tz_name, points=points)
    return resp.model_dump(mode="json")


# ---------------------------------------------------------------------------
# topics / parts（learning.md §6/§7，实时从事实表聚合）
# ---------------------------------------------------------------------------


async def get_topics_distribution(
    db: AsyncSession, *, current_user: User, months: int
) -> dict[str, Any]:
    """主题分布（learning.md §6.4）。

    - 按用户时区算 N 月前起始日 → 转 UTC 范围
    - 实时从 attempts JOIN sq JOIN recordings 聚合
    - GROUP BY snapshot.topic_id, topic_name，COUNT/SUM
    - ORDER BY attempt_count DESC
    """
    tz_name = await repo.get_user_timezone(db, current_user.id)
    tz = repo.get_timezone(tz_name)
    today = repo.today_in_timezone(tz)
    start_local = repo.add_months(today, -months)
    # 转 UTC 时间窗口：本地 00:00 → UTC，本地 23:59 → UTC
    # 简化：用本地 start 00:00 的 UTC 时间作为下界，本地 today 23:59 的 UTC 时间作为上界
    start_utc = datetime.combine(start_local, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    end_local = today + timedelta(days=1)
    end_utc = datetime.combine(end_local, datetime.min.time(), tzinfo=tz).astimezone(UTC)

    rows = await repo.get_topics_distribution(db, current_user.id, start_utc, end_utc)
    topics = [TopicStat(**r) for r in rows]
    resp = TopicsDistributionResponse(
        range_months=months, timezone=tz_name, topics=topics
    )
    return resp.model_dump(mode="json")


async def get_parts_distribution(
    db: AsyncSession, *, current_user: User, months: int
) -> dict[str, Any]:
    """Part 分布（learning.md §7.3）。同 topics，GROUP BY snapshot.part。"""
    tz_name = await repo.get_user_timezone(db, current_user.id)
    tz = repo.get_timezone(tz_name)
    today = repo.today_in_timezone(tz)
    start_local = repo.add_months(today, -months)
    start_utc = datetime.combine(start_local, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    end_local = today + timedelta(days=1)
    end_utc = datetime.combine(end_local, datetime.min.time(), tzinfo=tz).astimezone(UTC)

    rows = await repo.get_parts_distribution(db, current_user.id, start_utc, end_utc)
    parts = [PartStat(**r) for r in rows]
    resp = PartsDistributionResponse(
        range_months=months, timezone=tz_name, parts=parts
    )
    return resp.model_dump(mode="json")


# ---------------------------------------------------------------------------
# recompute（learning.md §8，admin 鉴权）
# ---------------------------------------------------------------------------


async def recompute(
    db: AsyncSession, *, admin: User, payload: RecomputeRequest
) -> dict[str, Any]:
    """重算 study_records（learning.md §8.4）。

    1. admin 鉴权由 router 层 require_admin 完成（2003）
    2. 解析 user_id / start_date / end_date
       - user_id 非法 → 1001
       - user_id 指定的用户不存在 → 7001
    3. 对每个目标用户（单用户或全量）：
       a. 取 user.timezone
       b. 事务内 DELETE+INSERT
    4. 累加统计 + 写 activity_log
    5. 返回汇总
    """
    target_user_ids = await _resolve_target_users(db, payload)
    start_date = payload.start_date
    end_date = payload.end_date

    recomputed_users = 0
    recomputed_records = 0
    deleted_records = 0
    duration_total = 0

    for uid in target_user_ids:
        tz_name = await repo.get_user_timezone(db, uid)
        stats = await repo.recompute_for_user(
            db,
            uid,
            timezone_name=tz_name,
            start_date=start_date,
            end_date=end_date,
        )
        recomputed_users += 1
        recomputed_records += stats["recomputed_records"]
        deleted_records += stats["deleted_records"]
        duration_total += stats["duration_seconds_total"]

        # 活动日志（learning.md §9.5）
        log = repo.build_recompute_log(
            admin_id=admin.id,
            target_user_id=uid,
            recomputed_records=stats["recomputed_records"],
            deleted_records=stats["deleted_records"],
        )
        db.add(log)

    await db.flush()

    resp = RecomputeResponse(
        recomputed_users=recomputed_users,
        recomputed_records=recomputed_records,
        deleted_records=deleted_records,
        duration_seconds_total=duration_total,
    )
    return resp.model_dump(mode="json")


async def _resolve_target_users(
    db: AsyncSession, payload: RecomputeRequest
) -> list[int]:
    """解析目标用户列表（learning.md §8.4 step 2）。

    - user_id 指定：校验合法数字(1001) + 用户存在(7001) → [uid]
    - 不指定：全量用户（list_user_ids）
    """
    if payload.user_id is not None:
        uid = _parse_user_id(payload.user_id)
        if not await repo.user_exists(db, uid):
            raise AppError(
                code=7001,
                message="用户不存在",
                http_status=404,
                details=[{"field": "user_id", "message": f"user {uid} not found"}],
            )
        return [uid]
    return await repo.list_user_ids(db)


def _parse_user_id(raw: str) -> int:
    """user_id 字符串 → int；非合法数字 → 1001/422。"""
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "user_id", "message": "user_id must be a positive integer"}],
        ) from exc
