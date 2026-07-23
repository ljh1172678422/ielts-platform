"""Practice 模块 SQLAlchemy 查询封装（system-architecture §3）。

对齐 practice.md §2.4/§3.4/§4.4/§5.5/§8.4：
- 创建会话：校验 topic 存在 → 统计可用题数 → 随机抽题 → 事务内 INSERT session + sq(snapshots)
- 获取会话：session + session_questions(sort_order) + attempts(attempt_number) LEFT JOIN recordings
- 创建 attempt：attempt_number = MAX+1，首次创建激活 session(created→in_progress)
- 更新 attempt：状态机校验由 service 层做，repo 仅 UPDATE + 时间戳
- 完成会话：ADR-015 校验由 service 层做，repo 仅 UPDATE session 终态

抽题仅查 status='published'（practice.md §2.4 step 3）。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.practice import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionQuestion,
    Recording,
)
from app.models.question import SpeakingQuestion, SpeakingTopic

# 用户端可见状态：仅 published（practice.md §2.4 step 3）
_PUBLISHED = "published"

# 会话状态（practice.md §2.2）
_SESSION_CREATED = "created"
_SESSION_IN_PROGRESS = "in_progress"


# ---------------------------------------------------------------------------
# 创建会话（practice.md §2.4）
# ---------------------------------------------------------------------------


async def get_topic_by_id(db: AsyncSession, topic_id: int) -> SpeakingTopic | None:
    """按 id 查主题（含软删除的不返回，practice.md §2.4 step 2）。"""
    stmt = select(SpeakingTopic).where(
        SpeakingTopic.id == topic_id,
        SpeakingTopic.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def count_available_questions(
    db: AsyncSession,
    *,
    part: int | None = None,
    topic_id: int | None = None,
) -> int:
    """统计可抽题数（published，叠加 part/topic 过滤，practice.md §2.4 step 4）。"""
    stmt = select(func.count()).select_from(SpeakingQuestion).where(
        SpeakingQuestion.status == _PUBLISHED
    )
    if part is not None:
        stmt = stmt.where(SpeakingQuestion.part == part)
    if topic_id is not None:
        stmt = stmt.where(SpeakingQuestion.topic_id == topic_id)
    result = await db.execute(stmt)
    return int(result.scalar_one())


async def sample_published_questions(
    db: AsyncSession,
    *,
    count: int,
    part: int | None = None,
    topic_id: int | None = None,
) -> list[SpeakingQuestion]:
    """随机抽题（ORDER BY RANDOM() LIMIT n，practice.md §2.4 step 5）。

    返回的 question 已加载 topic（构造 snapshot 需要 topic_name）。
    """
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic))
        .where(SpeakingQuestion.status == _PUBLISHED)
    )
    if part is not None:
        stmt = stmt.where(SpeakingQuestion.part == part)
    if topic_id is not None:
        stmt = stmt.where(SpeakingQuestion.topic_id == topic_id)
    stmt = stmt.order_by(func.random()).limit(count)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


def build_question_snapshot(question: SpeakingQuestion) -> dict[str, Any]:
    """构造题目快照（practice.md §2.4 step 6 / PROJECT_SPEC §4.5.5）。

    含 part/title/content/cue_card/topic_name/difficulty，不可变（ADR-016）。
    """
    return {
        "part": question.part,
        "title": question.title,
        "content": question.content,
        "cue_card": question.cue_card,
        "topic_name": question.topic.name if question.topic is not None else None,
        "difficulty": question.difficulty,
    }


async def insert_session(
    db: AsyncSession,
    *,
    user_id: int,
    mode: str,
    part_filter: int | None,
    topic_filter: int | None,
    question_count: int,
) -> PracticeSession:
    """INSERT 会话主表（status='created'，practice.md §2.4 step 6）。"""
    session = PracticeSession(
        user_id=user_id,
        mode=mode,
        part_filter=part_filter,
        topic_filter=topic_filter,
        question_count=question_count,
        status=_SESSION_CREATED,
    )
    db.add(session)
    await db.flush()
    return session


async def insert_session_questions(
    db: AsyncSession,
    *,
    session_id: int,
    questions: list[SpeakingQuestion],
) -> list[PracticeSessionQuestion]:
    """INSERT 会话题目（含 snapshot，sort_order 1..n，practice.md §2.4 step 6）。"""
    items: list[PracticeSessionQuestion] = []
    for idx, question in enumerate(questions, start=1):
        sq = PracticeSessionQuestion(
            session_id=session_id,
            question_id=question.id,
            question_snapshot=build_question_snapshot(question),
            sort_order=idx,
        )
        db.add(sq)
        items.append(sq)
    await db.flush()
    return items


# ---------------------------------------------------------------------------
# 获取会话（practice.md §3.4）
# ---------------------------------------------------------------------------


async def get_session_by_id(db: AsyncSession, session_id: int) -> PracticeSession | None:
    """按 id 查会话（practice.md §3.4 step 1）。"""
    stmt = select(PracticeSession).where(PracticeSession.id == session_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_session_questions(
    db: AsyncSession, session_id: int
) -> list[PracticeSessionQuestion]:
    """查询会话题目（按 sort_order，practice.md §3.4 step 3）。"""
    stmt = (
        select(PracticeSessionQuestion)
        .where(PracticeSessionQuestion.session_id == session_id)
        .order_by(PracticeSessionQuestion.sort_order)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_attempts_for_sqs(
    db: AsyncSession, sq_ids: list[int]
) -> dict[int, list[tuple[PracticeAttempt, Recording | None]]]:
    """批量查询 sq 的 attempts（按 attempt_number，LEFT JOIN recordings）。

    返回 {sq_id: [(attempt, recording), ...]}，避免 N+1（practice.md §3.4 step 4）。
    Phase 7 recording 恒为 None（录音上传在 Phase 8）。
    """
    if not sq_ids:
        return {}
    stmt = (
        select(PracticeAttempt, Recording)
        .outerjoin(Recording, Recording.attempt_id == PracticeAttempt.id)
        .where(PracticeAttempt.session_question_id.in_(sq_ids))
        .order_by(PracticeAttempt.session_question_id, PracticeAttempt.attempt_number)
    )
    result = await db.execute(stmt)
    mapping: dict[int, list[tuple[PracticeAttempt, Recording | None]]] = {}
    for attempt, recording in result.all():
        mapping.setdefault(attempt.session_question_id, []).append((attempt, recording))
    return mapping


# ---------------------------------------------------------------------------
# 创建 attempt（practice.md §4.4）
# ---------------------------------------------------------------------------


async def get_session_question_by_id(
    db: AsyncSession, sq_id: int
) -> PracticeSessionQuestion | None:
    """按 id 查会话题目（practice.md §4.4 step 1）。"""
    stmt = select(PracticeSessionQuestion).where(
        PracticeSessionQuestion.id == sq_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def next_attempt_number(
    db: AsyncSession, session_question_id: int
) -> int:
    """计算下一 attempt_number = MAX(attempt_number)+1（无则 1，practice.md §4.4 step 4）。"""
    stmt = select(func.max(PracticeAttempt.attempt_number)).where(
        PracticeAttempt.session_question_id == session_question_id
    )
    result = await db.execute(stmt)
    current = result.scalar_one_or_none()
    return (current or 0) + 1


async def insert_attempt(
    db: AsyncSession,
    *,
    session_question_id: int,
    user_id: int,
    attempt_number: int,
) -> PracticeAttempt:
    """INSERT attempt（status='pending'，practice.md §4.4 step 4）。"""
    attempt = PracticeAttempt(
        session_question_id=session_question_id,
        user_id=user_id,
        attempt_number=attempt_number,
        status="pending",
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def activate_session(db: AsyncSession, session_id: int) -> None:
    """激活会话：created → in_progress，填 started_at（practice.md §4.4 step 3）。"""
    stmt = select(PracticeSession).where(PracticeSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is not None and session.status == _SESSION_CREATED:
        session.status = _SESSION_IN_PROGRESS
        session.started_at = datetime.now(UTC)
        await db.flush()


# ---------------------------------------------------------------------------
# 更新 attempt（practice.md §5.5）
# ---------------------------------------------------------------------------


async def get_attempt_by_id(
    db: AsyncSession, attempt_id: int
) -> PracticeAttempt | None:
    """按 id 查 attempt（practice.md §5.5 step 1）。"""
    stmt = select(PracticeAttempt).where(PracticeAttempt.id == attempt_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_attempt_status(
    db: AsyncSession,
    attempt: PracticeAttempt,
    *,
    target_status: str,
) -> PracticeAttempt:
    """UPDATE attempt.status + 时间戳（practice.md §5.5 step 5）。

    状态转换合法性由 service 层校验（§5.3），repo 仅执行：
    - → recording：started_at=NOW()
    - → skipped：submitted_at=NOW()
    - → failed：不填 submitted_at
    """
    attempt.status = target_status
    if target_status == "recording":
        attempt.started_at = datetime.now(UTC)
    elif target_status == "skipped":
        attempt.submitted_at = datetime.now(UTC)
    await db.flush()
    return attempt


async def get_session_of_attempt(
    db: AsyncSession, attempt: PracticeAttempt
) -> PracticeSession | None:
    """通过 attempt → sq → session 查会话（practice.md §5.5 step 3 间接校验）。"""
    stmt = (
        select(PracticeSession)
        .join(
            PracticeSessionQuestion,
            PracticeSessionQuestion.session_id == PracticeSession.id,
        )
        .where(PracticeSessionQuestion.id == attempt.session_question_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 完成会话（practice.md §8.4）
# ---------------------------------------------------------------------------


async def get_attempt_status_summary(
    db: AsyncSession, session_id: int
) -> dict[int, set[str]]:
    """聚合每个 sq 的 attempt 状态集合（ADR-015 校验用，practice.md §8.4 step 4）。

    返回 {sq_id: {status, ...}}。service 层判断每个 sq 是否有 submitted/skipped。
    """
    stmt = (
        select(
            PracticeSessionQuestion.id,
            PracticeAttempt.status,
        )
        .select_from(PracticeSessionQuestion)
        .outerjoin(
            PracticeAttempt,
            PracticeAttempt.session_question_id == PracticeSessionQuestion.id,
        )
        .where(PracticeSessionQuestion.session_id == session_id)
    )
    result = await db.execute(stmt)
    mapping: dict[int, set[str]] = {}
    for sq_id, status in result.all():
        mapping.setdefault(sq_id, set())
        if status is not None:
            mapping[sq_id].add(status)
    return mapping


async def complete_session(
    db: AsyncSession, session: PracticeSession
) -> PracticeSession:
    """UPDATE session 终态（practice.md §8.4 step 5）。

    duration_seconds = completed_at - started_at（墙钟时长，仅展示，ADR-016）。
    ADR-015 校验由 service 层在调用前完成。
    """
    now = datetime.now(UTC)
    session.status = "completed"
    session.completed_at = now
    if session.started_at is not None:
        delta = now - session.started_at
        session.duration_seconds = int(delta.total_seconds())
    await db.flush()
    return session
