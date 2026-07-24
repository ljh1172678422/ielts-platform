"""Learning 模块测试（Phase 9.1-9.4）。

覆盖关键业务约束（learning.md）：
- overview: today(无记录补零)/streak(连续天数)/cumulative(SUM)/goal_progress(无 active goal 全 null)
- daily: 补零 + timezone 切日 + ASC 排序
- weekly: 周一~周日分组 + 补零
- monthly: 自然月分组 + 补零
- topics/parts: 实时从事实表聚合（snapshot 读取）
- recompute: admin 鉴权(2003)/user_id 校验(7001)/user_id 非法(1001)/DELETE+INSERT 事务
- schemas: days/weeks/months 越界 → 1001
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.activity import StudyRecord
from app.models.user import UserGoal
from app.modules.learning import service as learning_service
from app.modules.learning.schemas import (
    validate_days,
    validate_months,
    validate_weeks,
)

# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


def _make_study_record(
    *,
    rid: int = 1,
    user_id: int = 1,
    record_date: date,
    practice_count: int = 1,
    question_count: int = 5,
    attempt_count: int = 5,
    recording_count: int = 5,
    duration_seconds: int = 432,
) -> StudyRecord:
    return StudyRecord(
        id=rid,
        user_id=user_id,
        record_date=record_date,
        practice_count=practice_count,
        question_count=question_count,
        attempt_count=attempt_count,
        recording_count=recording_count,
        duration_seconds=duration_seconds,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# schemas 范围校验（learning.md §3.1/§4.1/§5.1/§6.1）
# ---------------------------------------------------------------------------


def test_validate_days_below_min_returns_1001() -> None:
    with pytest.raises(AppError) as exc:
        validate_days(0)
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


def test_validate_days_above_max_returns_1001() -> None:
    with pytest.raises(AppError) as exc:
        validate_days(91)
    assert exc.value.code == 1001


def test_validate_weeks_below_min_returns_1001() -> None:
    with pytest.raises(AppError) as exc:
        validate_weeks(0)
    assert exc.value.code == 1001


def test_validate_months_above_max_returns_1001() -> None:
    with pytest.raises(AppError) as exc:
        validate_months(25)
    assert exc.value.code == 1001


def test_validate_ranges_pass_for_valid_values() -> None:
    """合法范围不应抛错。"""
    validate_days(1)
    validate_days(90)
    validate_weeks(1)
    validate_weeks(52)
    validate_months(1)
    validate_months(24)


# ---------------------------------------------------------------------------
# overview（learning.md §2）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_no_records_returns_all_zero() -> None:
    """无任何 study_record → today 全 0，streak 0/0，cumulative 全 0，goal 全 null。"""
    db = _mock_db()
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.get_study_record_for_date", new=AsyncMock(return_value=None)),
        patch("app.modules.learning.service.repo.get_all_record_dates", new=AsyncMock(return_value=[])),
        patch("app.modules.learning.service.repo.get_cumulative_stats", new=AsyncMock(return_value={
            "total_sessions": 0, "total_questions": 0, "total_attempts": 0,
            "total_recordings": 0, "total_duration_seconds": 0,
        })),
        patch("app.modules.learning.service.repo.get_active_goal", new=AsyncMock(return_value=None)),
    ):
        result = await learning_service.get_overview(db, current_user=MagicMock(id=1))
    assert result["today"]["practice_count"] == 0
    assert result["today"]["duration_seconds"] == 0
    assert result["streak"]["current_days"] == 0
    assert result["streak"]["longest_days"] == 0
    assert result["cumulative"]["total_sessions"] == 0
    assert result["goal_progress"]["daily_goal_minutes"] is None
    assert result["goal_progress"]["daily_completed_minutes"] is None


@pytest.mark.asyncio
async def test_overview_today_has_record_returns_today_stats() -> None:
    """今日有 study_record → today 字段填充。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    today_rec = _make_study_record(record_date=today, duration_seconds=432)
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.get_study_record_for_date", new=AsyncMock(return_value=today_rec)),
        patch("app.modules.learning.service.repo.get_all_record_dates", new=AsyncMock(return_value=[today])),
        patch("app.modules.learning.service.repo.get_cumulative_stats", new=AsyncMock(return_value={
            "total_sessions": 42, "total_questions": 198, "total_attempts": 210,
            "total_recordings": 195, "total_duration_seconds": 16830,
        })),
        patch("app.modules.learning.service.repo.get_active_goal", new=AsyncMock(return_value=None)),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
    ):
        result = await learning_service.get_overview(db, current_user=MagicMock(id=1))
    assert result["today"]["practice_count"] == 1
    assert result["today"]["duration_seconds"] == 432
    assert result["cumulative"]["total_sessions"] == 42
    assert result["cumulative"]["total_duration_seconds"] == 16830
    # 今日有数据，streak current_days=1
    assert result["streak"]["current_days"] == 1


@pytest.mark.asyncio
async def test_overview_streak_computes_current_and_longest() -> None:
    """连续 7 天 + 中间断 1 天 → current=7（今日起）/ longest=7。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    # 连续 7 天：7.17-7.23
    dates = [today - timedelta(days=i) for i in range(7)]
    # 另有一段 5 天前连续 3 天
    dates += [date(2026, 7, 5), date(2026, 7, 6), date(2026, 7, 7)]
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.get_study_record_for_date", new=AsyncMock(return_value=_make_study_record(record_date=today))),
        patch("app.modules.learning.service.repo.get_all_record_dates", new=AsyncMock(return_value=dates)),
        patch("app.modules.learning.service.repo.get_cumulative_stats", new=AsyncMock(return_value={
            "total_sessions": 0, "total_questions": 0, "total_attempts": 0,
            "total_recordings": 0, "total_duration_seconds": 0,
        })),
        patch("app.modules.learning.service.repo.get_active_goal", new=AsyncMock(return_value=None)),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
    ):
        result = await learning_service.get_overview(db, current_user=MagicMock(id=1))
    assert result["streak"]["current_days"] == 7
    assert result["streak"]["longest_days"] == 7


@pytest.mark.asyncio
async def test_overview_today_no_data_current_days_zero() -> None:
    """今日无数据但昨日有 → current_days=0（MVP 简化）。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    yesterday = today - timedelta(days=1)
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.get_study_record_for_date", new=AsyncMock(return_value=None)),
        patch("app.modules.learning.service.repo.get_all_record_dates", new=AsyncMock(return_value=[yesterday])),
        patch("app.modules.learning.service.repo.get_cumulative_stats", new=AsyncMock(return_value={
            "total_sessions": 0, "total_questions": 0, "total_attempts": 0,
            "total_recordings": 0, "total_duration_seconds": 0,
        })),
        patch("app.modules.learning.service.repo.get_active_goal", new=AsyncMock(return_value=None)),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
    ):
        result = await learning_service.get_overview(db, current_user=MagicMock(id=1))
    assert result["streak"]["current_days"] == 0
    assert result["streak"]["longest_days"] == 1


@pytest.mark.asyncio
async def test_overview_active_goal_returns_progress_minutes() -> None:
    """有 active goal → goal_progress 含 daily/weekly 目标与完成分钟数。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    today_rec = _make_study_record(record_date=today, duration_seconds=432)
    goal = MagicMock(spec=UserGoal)
    goal.daily_goal_minutes = 60
    goal.weekly_goal_minutes = 360
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.get_study_record_for_date", new=AsyncMock(return_value=today_rec)),
        patch("app.modules.learning.service.repo.get_all_record_dates", new=AsyncMock(return_value=[today])),
        patch("app.modules.learning.service.repo.get_cumulative_stats", new=AsyncMock(return_value={
            "total_sessions": 0, "total_questions": 0, "total_attempts": 0,
            "total_recordings": 0, "total_duration_seconds": 0,
        })),
        patch("app.modules.learning.service.repo.get_active_goal", new=AsyncMock(return_value=goal)),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
        patch("app.modules.learning.service.repo.sum_study_records_for_dates", new=AsyncMock(return_value={"duration_seconds": 3150})),
    ):
        result = await learning_service.get_overview(db, current_user=MagicMock(id=1))
    # today 432s → 7.2 分钟
    assert result["goal_progress"]["daily_goal_minutes"] == 60
    assert result["goal_progress"]["daily_completed_minutes"] == 7.2
    assert result["goal_progress"]["weekly_goal_minutes"] == 360
    # 3150s → 52.5 分钟
    assert result["goal_progress"]["weekly_completed_minutes"] == 52.5


# ---------------------------------------------------------------------------
# daily（learning.md §3）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_trend_fills_missing_days_with_zero() -> None:
    """N 天范围内缺失日期补零，按 date ASC。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    yesterday = today - timedelta(days=1)
    records = [_make_study_record(rid=1, record_date=yesterday, duration_seconds=720)]
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
        patch("app.modules.learning.service.repo.get_study_records_in_range", new=AsyncMock(return_value=records)),
    ):
        result = await learning_service.get_daily_trend(db, current_user=MagicMock(id=1), days=3)
    assert result["granularity"] == "daily"
    assert result["timezone"] == "Asia/Shanghai"
    assert len(result["points"]) == 3
    # ASC 排序：昨天、前天、今日
    assert result["points"][0]["date"] == "2026-07-21"
    assert result["points"][0]["duration_seconds"] == 0  # 补零
    assert result["points"][1]["date"] == "2026-07-22"
    assert result["points"][1]["duration_seconds"] == 720  # 有数据
    assert result["points"][2]["date"] == "2026-07-23"
    assert result["points"][2]["duration_seconds"] == 0  # 今日补零


# ---------------------------------------------------------------------------
# weekly（learning.md §4）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weekly_trend_groups_by_monday_and_fills_zero() -> None:
    """按周一分组求和 + 补零，返回 week_start/week_end。"""
    db = _mock_db()
    today = date(2026, 7, 23)  # 周四
    # 本周一 7.20，上周一 7.13
    this_monday = date(2026, 7, 20)
    last_monday = date(2026, 7, 13)
    records = [
        _make_study_record(rid=1, record_date=this_monday, duration_seconds=600),
        _make_study_record(rid=2, record_date=this_monday + timedelta(days=1), duration_seconds=400),
        _make_study_record(rid=3, record_date=last_monday, duration_seconds=300),
    ]
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
        patch("app.modules.learning.service.repo.get_study_records_in_range", new=AsyncMock(return_value=records)),
    ):
        result = await learning_service.get_weekly_trend(db, current_user=MagicMock(id=1), weeks=3)
    assert result["granularity"] == "weekly"
    assert len(result["points"]) == 3
    # ASC 排序
    assert result["points"][0]["week_start"] == "2026-07-06"  # 三周前周一
    assert result["points"][0]["week_end"] == "2026-07-12"
    assert result["points"][0]["duration_seconds"] == 0  # 补零
    assert result["points"][1]["week_start"] == "2026-07-13"
    assert result["points"][1]["duration_seconds"] == 300
    assert result["points"][2]["week_start"] == "2026-07-20"
    assert result["points"][2]["week_end"] == "2026-07-26"
    assert result["points"][2]["duration_seconds"] == 1000  # 600+400


# ---------------------------------------------------------------------------
# monthly（learning.md §5）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monthly_trend_groups_by_month_and_fills_zero() -> None:
    """按自然月分组求和 + 补零，返回 YYYY-MM。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    records = [
        _make_study_record(rid=1, record_date=date(2026, 7, 1), duration_seconds=500),
        _make_study_record(rid=2, record_date=date(2026, 6, 15), duration_seconds=200),
    ]
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
        patch("app.modules.learning.service.repo.get_study_records_in_range", new=AsyncMock(return_value=records)),
    ):
        result = await learning_service.get_monthly_trend(db, current_user=MagicMock(id=1), months=3)
    assert result["granularity"] == "monthly"
    assert len(result["points"]) == 3
    assert result["points"][0]["month"] == "2026-05"
    assert result["points"][0]["duration_seconds"] == 0
    assert result["points"][1]["month"] == "2026-06"
    assert result["points"][1]["duration_seconds"] == 200
    assert result["points"][2]["month"] == "2026-07"
    assert result["points"][2]["duration_seconds"] == 500


# ---------------------------------------------------------------------------
# topics / parts（learning.md §6/§7，走事实表）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topics_distribution_returns_repo_rows() -> None:
    """topics 直接返回 repo 聚合结果（按 attempt_count DESC）。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    rows = [
        {"topic_id": "5", "topic_name": "Technology", "attempt_count": 24, "duration_seconds": 1980},
        {"topic_id": "8", "topic_name": "Travel", "attempt_count": 15, "duration_seconds": 1200},
    ]
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
        patch("app.modules.learning.service.repo.get_topics_distribution", new=AsyncMock(return_value=rows)),
    ):
        result = await learning_service.get_topics_distribution(db, current_user=MagicMock(id=1), months=3)
    assert result["range_months"] == 3
    assert result["timezone"] == "Asia/Shanghai"
    assert len(result["topics"]) == 2
    assert result["topics"][0]["topic_id"] == "5"
    assert result["topics"][0]["topic_name"] == "Technology"
    assert result["topics"][0]["attempt_count"] == 24


@pytest.mark.asyncio
async def test_parts_distribution_returns_repo_rows() -> None:
    """parts 直接返回 repo 聚合结果（按 part ASC）。"""
    db = _mock_db()
    today = date(2026, 7, 23)
    rows = [
        {"part": 1, "attempt_count": 30, "duration_seconds": 1500},
        {"part": 2, "attempt_count": 45, "duration_seconds": 3600},
    ]
    with (
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.today_in_timezone", return_value=today),
        patch("app.modules.learning.service.repo.get_parts_distribution", new=AsyncMock(return_value=rows)),
    ):
        result = await learning_service.get_parts_distribution(db, current_user=MagicMock(id=1), months=3)
    assert result["range_months"] == 3
    assert len(result["parts"]) == 2
    assert result["parts"][0]["part"] == 1
    assert result["parts"][1]["part"] == 2


# ---------------------------------------------------------------------------
# recompute（learning.md §8）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recompute_invalid_user_id_format_returns_1001() -> None:
    """user_id 非数字 → 1001/422。"""
    db = _mock_db()
    payload = MagicMock()
    payload.user_id = "abc"
    payload.start_date = None
    payload.end_date = None
    with pytest.raises(AppError) as exc:
        await learning_service.recompute(db, admin=MagicMock(id=99), payload=payload)
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


@pytest.mark.asyncio
async def test_recompute_user_not_found_returns_7001() -> None:
    """user_id 合法但用户不存在 → 7001/404。"""
    db = _mock_db()
    payload = MagicMock()
    payload.user_id = "9999"
    payload.start_date = None
    payload.end_date = None
    with patch("app.modules.learning.service.repo.user_exists", new=AsyncMock(return_value=False)):
        with pytest.raises(AppError) as exc:
            await learning_service.recompute(db, admin=MagicMock(id=99), payload=payload)
    assert exc.value.code == 7001
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_recompute_single_user_invokes_repo_and_writes_log() -> None:
    """单用户重算：调 recompute_for_user + 写 activity_log + 返回汇总。"""
    db = _mock_db()
    payload = MagicMock()
    payload.user_id = "1001"
    payload.start_date = None
    payload.end_date = None
    stats = {
        "recomputed_records": 10,
        "deleted_records": 2,
        "duration_seconds_total": 3120,
    }
    with (
        patch("app.modules.learning.service.repo.user_exists", new=AsyncMock(return_value=True)),
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.recompute_for_user", new=AsyncMock(return_value=stats)) as recompute_mock,
    ):
        result = await learning_service.recompute(db, admin=MagicMock(id=99), payload=payload)
    recompute_mock.assert_awaited_once()
    assert result["recomputed_users"] == 1
    assert result["recomputed_records"] == 10
    assert result["deleted_records"] == 2
    assert result["duration_seconds_total"] == 3120
    # 写了 activity_log
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert log_obj.action == "study_records_recomputed"
    assert log_obj.entity_type == "user"
    assert log_obj.entity_id == 1001
    assert log_obj.metadata_["recomputed_records"] == 10


@pytest.mark.asyncio
async def test_recompute_all_users_iterates_list() -> None:
    """不指定 user_id → 全量用户循环重算。"""
    db = _mock_db()
    payload = MagicMock()
    payload.user_id = None
    payload.start_date = None
    payload.end_date = None
    stats = {
        "recomputed_records": 5,
        "deleted_records": 1,
        "duration_seconds_total": 1500,
    }
    with (
        patch("app.modules.learning.service.repo.list_user_ids", new=AsyncMock(return_value=[1, 2, 3])),
        patch("app.modules.learning.service.repo.get_user_timezone", new=AsyncMock(return_value="Asia/Shanghai")),
        patch("app.modules.learning.service.repo.recompute_for_user", new=AsyncMock(return_value=stats)),
    ):
        result = await learning_service.recompute(db, admin=MagicMock(id=99), payload=payload)
    assert result["recomputed_users"] == 3
    assert result["recomputed_records"] == 15  # 5*3
    assert result["deleted_records"] == 3  # 1*3
    assert result["duration_seconds_total"] == 4500  # 1500*3


# ---------------------------------------------------------------------------
# repository 工具函数（learning.md §4.1/§5.1）
# ---------------------------------------------------------------------------


def test_week_monday_returns_iso_monday() -> None:
    """周一为 ISO 8601 周起始（learning.md §4.1）。"""
    from app.modules.learning.repository import week_monday
    # 2026-07-23 是周四
    assert week_monday(date(2026, 7, 23)) == date(2026, 7, 20)
    # 2026-07-20 是周一
    assert week_monday(date(2026, 7, 20)) == date(2026, 7, 20)
    # 2026-07-26 是周日
    assert week_monday(date(2026, 7, 26)) == date(2026, 7, 20)


def test_month_start_returns_first_day() -> None:
    """月首（learning.md §5.1）。"""
    from app.modules.learning.repository import month_start
    assert month_start(date(2026, 7, 23)) == date(2026, 7, 1)
    assert month_start(date(2026, 2, 28)) == date(2026, 2, 1)


def test_add_months_handles_month_end_truncation() -> None:
    """加月后日超出月末则截到月末（如 1.31 + 1 月 = 2.28）。"""
    from app.modules.learning.repository import add_months
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 7, 23), -3) == date(2026, 4, 23)
    assert add_months(date(2026, 7, 23), 12) == date(2027, 7, 23)


# ---------------------------------------------------------------------------
# streak 算法细节（learning.md §2.4）
# ---------------------------------------------------------------------------


def test_compute_streak_empty_returns_zero_zero() -> None:
    """无任何日期 → (0, 0)。"""
    from app.modules.learning.service import _compute_streak
    assert _compute_streak([], date(2026, 7, 23)) == (0, 0)


def test_compute_streak_single_day_today_returns_one_one() -> None:
    """仅今日有数据 → current=1, longest=1。"""
    from app.modules.learning.service import _compute_streak
    today = date(2026, 7, 23)
    assert _compute_streak([today], today) == (1, 1)


def test_compute_streak_longest_segment_wins() -> None:
    """两段：早段 5 天 + 晚段 3 天（含今日）→ current=3, longest=5。"""
    from app.modules.learning.service import _compute_streak
    today = date(2026, 7, 23)
    late = [today - timedelta(days=i) for i in range(3)]  # 7.21-7.23
    early = [date(2026, 6, 1) + timedelta(days=i) for i in range(5)]  # 6.1-6.5
    assert _compute_streak(late + early, today) == (3, 5)
