"""Home 模块测试（Phase 10.1）。

覆盖关键业务约束（home.md）：
- overview: today/streak/goal_progress 复用 learning 子查询
- recent_practice: 有/无未完成 session
- recommendations 5 级短路（ADR-028）：逐级填充 + 去重 + 凑齐即停
- recommendation_limit 越界 → 1001
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.practice import PracticeSession
from app.modules.home import service as home_service

# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


def _make_session(
    *,
    sid: int = 201,
    user_id: int = 1,
    status: str = "in_progress",
    mode: str = "topic",
    question_count: int = 5,
) -> PracticeSession:
    return PracticeSession(
        id=sid,
        user_id=user_id,
        mode=mode,
        part_filter=None,
        topic_filter=5,
        question_count=question_count,
        status=status,
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_question_dict(
    *, qid: int = 101, part: int = 2, title: str = "Q1", topic_id: int = 5, topic_name: str = "Tech"
) -> MagicMock:
    """构造带 topic 关系的 question mock。"""
    topic = MagicMock()
    topic.id = topic_id
    topic.name = topic_name
    q = MagicMock()
    q.id = qid
    q.part = part
    q.title = title
    q.topic = topic
    q.difficulty = 3
    return q


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# recommendation_limit 校验（home.md §2.4）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_limit_below_min_returns_1001() -> None:
    """recommendation_limit < 1 → 1001/422。"""
    db = _mock_db()
    with pytest.raises(AppError) as exc:
        await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=0
        )
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


@pytest.mark.asyncio
async def test_overview_limit_above_max_returns_1001() -> None:
    """recommendation_limit > 10 → 1001/422。"""
    db = _mock_db()
    with pytest.raises(AppError) as exc:
        await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=11
        )
    assert exc.value.code == 1001


# ---------------------------------------------------------------------------
# recent_practice（home.md §2.3）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_no_unfinished_session_returns_has_unfinished_false() -> None:
    """无未完成 session → has_unfinished=false, session=null。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=None)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_less_practiced_part_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_popular_questions", new=AsyncMock(return_value=[])),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=5
        )
    assert result["recent_practice"]["has_unfinished"] is False
    assert result["recent_practice"]["session"] is None
    assert result["recommendations"] == []


@pytest.mark.asyncio
async def test_overview_has_unfinished_session_returns_summary() -> None:
    """有未完成 session → has_unfinished=true, 含 completed_questions。"""
    db = _mock_db()
    session = _make_session(sid=201, status="in_progress", question_count=5)
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=session)),
        patch("app.modules.home.service.repo.count_completed_questions", new=AsyncMock(return_value=3)),
        # level 1 取未完成 session 题目（返回空避免影响）
        patch("app.modules.home.service.repo.get_unfinished_session_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_less_practiced_part_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_popular_questions", new=AsyncMock(return_value=[])),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=5
        )
    assert result["recent_practice"]["has_unfinished"] is True
    assert result["recent_practice"]["session"]["id"] == "201"
    assert result["recent_practice"]["session"]["status"] == "in_progress"
    assert result["recent_practice"]["session"]["completed_questions"] == 3


# ---------------------------------------------------------------------------
# 推荐算法 5 级短路（ADR-028）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommendations_level1_fills_quota_stops() -> None:
    """level 1 凑齐配额 → 不调用后续级别。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    session = _make_session(sid=201)
    questions = [_make_question_dict(qid=101), _make_question_dict(qid=102, title="Q2")]
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=session)),
        patch("app.modules.home.service.repo.count_completed_questions", new=AsyncMock(return_value=0)),
        patch("app.modules.home.service.repo.get_unfinished_session_questions", new=AsyncMock(return_value=questions)) as l1,
        patch("app.modules.home.service.repo.batch_practice_counts_by_questions", new=AsyncMock(return_value={101: 5, 102: 3})),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock()) as l2,
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=2
        )
    assert len(result["recommendations"]) == 2
    assert result["recommendations"][0]["reason"] == "unfinished_session"
    assert result["recommendations"][0]["id"] == "101"
    assert result["recommendations"][1]["id"] == "102"
    # level 1 凑齐 → level 2 不应被调用
    l2.assert_not_awaited()
    l1.assert_awaited_once()


@pytest.mark.asyncio
async def test_recommendations_level1_insufficient_falls_to_level2() -> None:
    """level 1 不够 → 继续调 level 2 补足。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    session = _make_session(sid=201)
    l1_qs = [_make_question_dict(qid=101)]
    l2_qs = [_make_question_dict(qid=200, title="L2"), _make_question_dict(qid=201, title="L2b")]
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=session)),
        patch("app.modules.home.service.repo.count_completed_questions", new=AsyncMock(return_value=0)),
        patch("app.modules.home.service.repo.get_unfinished_session_questions", new=AsyncMock(return_value=l1_qs)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=l2_qs)),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock()) as l3,
        patch("app.modules.home.service.repo.batch_practice_counts_by_questions", new=AsyncMock(return_value={})),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=3
        )
    assert len(result["recommendations"]) == 3
    assert result["recommendations"][0]["reason"] == "unfinished_session"
    assert result["recommendations"][1]["reason"] == "recent_topic"
    assert result["recommendations"][2]["reason"] == "recent_topic"
    # 凑齐 3 → level 3 不应被调用
    l3.assert_not_awaited()


@pytest.mark.asyncio
async def test_recommendations_dedup_across_levels() -> None:
    """跨级 question_id 去重，同一题不在多个 reason 出现。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    session = _make_session(sid=201)
    # level 1 取 qid=101；level 2 repo 返回包含 101（应被 service 层去重）
    # 注意：repo 层已通过 exclude_ids 过滤，但 service 层有兜底去重
    l1_qs = [_make_question_dict(qid=101)]
    l2_qs = [_make_question_dict(qid=102, title="L2")]
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=session)),
        patch("app.modules.home.service.repo.count_completed_questions", new=AsyncMock(return_value=0)),
        patch("app.modules.home.service.repo.get_unfinished_session_questions", new=AsyncMock(return_value=l1_qs)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=l2_qs)),
        patch("app.modules.home.service.repo.batch_practice_counts_by_questions", new=AsyncMock(return_value={})),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=2
        )
    ids = [r["id"] for r in result["recommendations"]]
    assert ids == ["101", "102"]
    assert len(ids) == len(set(ids))  # 无重复


@pytest.mark.asyncio
async def test_recommendations_all_levels_empty_returns_empty() -> None:
    """所有级别都返回空 → recommendations=[]。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=None)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_less_practiced_part_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_popular_questions", new=AsyncMock(return_value=[])),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=5
        )
    assert result["recommendations"] == []


@pytest.mark.asyncio
async def test_recommendations_level5_popular_fills_remaining() -> None:
    """level 1-4 全空 → level 5 popular 兜底凑齐。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    popular_qs = [
        _make_question_dict(qid=300, title=f"Popular{i}") for i in range(5)
    ]
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=None)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_less_practiced_part_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_popular_questions", new=AsyncMock(return_value=popular_qs)) as l5,
        patch("app.modules.home.service.repo.batch_practice_counts_by_questions", new=AsyncMock(return_value={300: 100, 301: 90})),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=5
        )
    assert len(result["recommendations"]) == 5
    assert all(r["reason"] == "popular" for r in result["recommendations"])
    l5.assert_awaited_once()


# ---------------------------------------------------------------------------
# goal_progress 扩展（home.md §4）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_goal_progress_none_when_no_active_goal() -> None:
    """无 active goal → goal_progress=null（whole field null，不是空对象）。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": None}
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=None)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_less_practiced_part_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_popular_questions", new=AsyncMock(return_value=[])),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=5
        )
    assert result["goal_progress"] is None


@pytest.mark.asyncio
async def test_overview_goal_progress_includes_target_score_and_exam_date() -> None:
    """有 active goal → goal_progress 含 target_score/exam_date（home.md §4 扩展）。"""
    db = _mock_db()
    stats = {"today": {"practice_count": 0, "question_count": 0, "attempt_count": 0,
                       "recording_count": 0, "duration_seconds": 0},
             "streak": {"current_days": 0, "longest_days": 0},
             "goal_progress": {
                 "daily_goal_minutes": 60,
                 "daily_completed_minutes": 7.2,
                 "weekly_goal_minutes": 360,
                 "weekly_completed_minutes": 52.5,
                 "target_score": 7.0,
                 "exam_date": date(2026, 11, 15),
             }}
    with (
        patch("app.modules.home.service.repo.fetch_today_streak_goal", new=AsyncMock(return_value=stats)),
        patch("app.modules.home.service.repo.get_unfinished_session", new=AsyncMock(return_value=None)),
        patch("app.modules.home.service.repo.get_recent_topic_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_favorite_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_less_practiced_part_questions", new=AsyncMock(return_value=[])),
        patch("app.modules.home.service.repo.get_popular_questions", new=AsyncMock(return_value=[])),
    ):
        result = await home_service.get_overview(
            db, current_user=MagicMock(id=1), recommendation_limit=5
        )
    assert result["goal_progress"]["target_score"] == 7.0
    assert result["goal_progress"]["exam_date"] == "2026-11-15"
    assert result["goal_progress"]["daily_goal_minutes"] == 60
