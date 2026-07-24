"""Home 模块业务逻辑（system-architecture §3：service 层）。

对齐 home.md §2.6：
- 聚合 today/streak/goal_progress（复用 learning 子查询）
- recent_practice：未完成 session
- recommendations：ADR-028 5 级短路，凑齐 recommendation_limit 即停
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.practice import PracticeSession
from app.models.user import User
from app.modules.home import repository as repo
from app.modules.home.schemas import HomeOverview, Recommendation

# 推荐配额范围（home.md §2.1）
_REC_LIMIT_MIN = 1
_REC_LIMIT_MAX = 10


async def get_overview(
    db: AsyncSession, *, current_user: User, recommendation_limit: int
) -> dict[str, Any]:
    """首页聚合（home.md §2.6）。

    1. 校验 recommendation_limit ∈ [1, 10]
    2. 取 today/streak/goal_progress（复用 learning 子查询）
    3. 取未完成 session → recent_practice
    4. 推荐生成（5 级短路）
    5. 组装返回
    """
    _validate_limit(recommendation_limit)

    # 1. today/streak/goal_progress
    stats = await repo.fetch_today_streak_goal(db, current_user.id)

    # 2. recent_practice
    unfinished = await repo.get_unfinished_session(db, current_user.id)
    recent_practice = await _build_recent_practice(db, unfinished)

    # 3. 推荐生成（5 级短路）
    recommendations = await _build_recommendations(
        db, current_user.id, unfinished=unfinished, limit=recommendation_limit
    )

    overview = HomeOverview(
        today=stats["today"],
        streak=stats["streak"],
        goal_progress=stats["goal_progress"],
        recent_practice=recent_practice,
        recommendations=[Recommendation(**r) for r in recommendations],
    )
    return overview.model_dump(mode="json")


def _validate_limit(limit: int) -> None:
    """recommendation_limit 越界 → 1001/422（home.md §2.4）。"""
    if not _REC_LIMIT_MIN <= limit <= _REC_LIMIT_MAX:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[
                {
                    "field": "recommendation_limit",
                    "message": (
                        f"recommendation_limit={limit} 越界，"
                        f"合法范围 [{_REC_LIMIT_MIN}, {_REC_LIMIT_MAX}]"
                    ),
                }
            ],
        )


async def _build_recent_practice(
    db: AsyncSession, unfinished: PracticeSession | None
) -> dict[str, Any]:
    """构造 recent_practice（home.md §2.6 step 2）。"""
    if unfinished is None:
        return {"has_unfinished": False, "session": None}

    completed = await repo.count_completed_questions(db, unfinished.id)
    return {
        "has_unfinished": True,
        "session": {
            "id": str(unfinished.id),
            "status": unfinished.status,
            "mode": unfinished.mode,
            "question_count": unfinished.question_count,
            "completed_questions": completed,
            "updated_at": unfinished.updated_at.isoformat(),
        },
    }


async def _build_recommendations(
    db: AsyncSession,
    user_id: int,
    *,
    unfinished: PracticeSession | None,
    limit: int,
) -> list[dict[str, Any]]:
    """5 级推荐短路（home.md §2.5，ADR-028）。

    每级取完更新剩余配额，剩余=0 则停止。
    跨级 question_id 去重，同一题不在多个 reason 出现。
    """
    result: list[dict[str, Any]] = []
    taken_ids: set[int] = set()
    remaining = limit

    # level 1: unfinished_session
    if remaining > 0 and unfinished is not None:
        questions = await repo.get_unfinished_session_questions(
            db, unfinished.id, exclude_ids=taken_ids, limit=remaining
        )
        if questions:
            counts = await repo.batch_practice_counts_by_questions(
                db, [q.id for q in questions]
            )
            result.extend(
                repo.to_recommendation_dict(
                    questions, reason="unfinished_session", practice_counts=counts
                )
            )
            taken_ids.update(q.id for q in questions)
            remaining = limit - len(result)

    # level 2: recent_topic
    if remaining > 0:
        questions = await repo.get_recent_topic_questions(
            db, user_id, exclude_ids=taken_ids, limit=remaining
        )
        if questions:
            counts = await repo.batch_practice_counts_by_questions(
                db, [q.id for q in questions]
            )
            result.extend(
                repo.to_recommendation_dict(
                    questions, reason="recent_topic", practice_counts=counts
                )
            )
            taken_ids.update(q.id for q in questions)
            remaining = limit - len(result)

    # level 3: favorite
    if remaining > 0:
        questions = await repo.get_favorite_questions(
            db, user_id, exclude_ids=taken_ids, limit=remaining
        )
        if questions:
            counts = await repo.batch_practice_counts_by_questions(
                db, [q.id for q in questions]
            )
            result.extend(
                repo.to_recommendation_dict(
                    questions, reason="favorite", practice_counts=counts
                )
            )
            taken_ids.update(q.id for q in questions)
            remaining = limit - len(result)

    # level 4: less_practiced_part
    if remaining > 0:
        questions = await repo.get_less_practiced_part_questions(
            db, user_id, exclude_ids=taken_ids, limit=remaining
        )
        if questions:
            counts = await repo.batch_practice_counts_by_questions(
                db, [q.id for q in questions]
            )
            result.extend(
                repo.to_recommendation_dict(
                    questions, reason="less_practiced_part", practice_counts=counts
                )
            )
            taken_ids.update(q.id for q in questions)
            remaining = limit - len(result)

    # level 5: popular（兜底）
    if remaining > 0:
        questions = await repo.get_popular_questions(
            db, exclude_ids=taken_ids, limit=remaining
        )
        if questions:
            counts = await repo.batch_practice_counts_by_questions(
                db, [q.id for q in questions]
            )
            result.extend(
                repo.to_recommendation_dict(
                    questions, reason="popular", practice_counts=counts
                )
            )
            taken_ids.update(q.id for q in questions)

    return result
