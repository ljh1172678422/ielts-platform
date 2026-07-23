"""Admin 模块 SQLAlchemy 查询封装（system-architecture §3）。

Phase 5.1 Dashboard：聚合统计查询。
后续 5.2-5.5 在本文件追加用户/主题/标签/题目 CRUD 查询。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.question import (
    QuestionTag,
    SpeakingQuestion,
    SpeakingTopic,
    Tag,
)
from app.models.user import Role, User, UserProfile

# ---------------------------------------------------------------------------
# Dashboard 统计（admin.md §2.4）
# ---------------------------------------------------------------------------


async def count_users_total(db: AsyncSession) -> int:
    """活跃用户总数（未软删）。"""
    stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    return int((await db.execute(stmt)).scalar_one())


async def count_users_active_today(db: AsyncSession) -> int:
    """今日有 study_record 的用户数（admin.md §2.4：按 UTC 统计）。

    MVP：study_records 表属学习域（Phase 7），此处先用 last_login_at 近似
    （今日登录过的用户数）。Phase 7 接入 study_records 后修正为真实活跃统计。
    """
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count()).select_from(User).where(
        User.deleted_at.is_(None),
        User.last_login_at >= today_start,
    )
    return int((await db.execute(stmt)).scalar_one())


async def count_users_new_this_week(db: AsyncSession) -> int:
    """本周（ISO 周，UTC）注册用户数。"""
    # 本周起始：往前找到周一（ISO 周一为周首）
    now = datetime.now(UTC)
    monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    stmt = select(func.count()).select_from(User).where(
        User.deleted_at.is_(None),
        User.created_at >= monday,
    )
    return int((await db.execute(stmt)).scalar_one())


async def count_questions_by_status(db: AsyncSession) -> dict[str, int]:
    """题目按 status 分组计数。"""
    stmt = select(SpeakingQuestion.status, func.count()).group_by(SpeakingQuestion.status)
    rows = (await db.execute(stmt)).all()
    counts = {"published": 0, "draft": 0, "disabled": 0}
    for status, cnt in rows:
        counts[status] = int(cnt)
    counts["total"] = sum(counts.values())
    return counts


async def count_topics_total(db: AsyncSession) -> int:
    """主题总数（未软删）。"""
    stmt = select(func.count()).select_from(SpeakingTopic).where(
        SpeakingTopic.deleted_at.is_(None)
    )
    return int((await db.execute(stmt)).scalar_one())


async def count_tags_total(db: AsyncSession) -> int:
    """标签总数（未软删）。"""
    stmt = select(func.count()).select_from(Tag).where(Tag.deleted_at.is_(None))
    return int((await db.execute(stmt)).scalar_one())


async def count_practice_stats(db: AsyncSession) -> dict[str, int]:
    """练习统计（sessions/attempts/recordings/duration）。

    Phase 5 MVP：practice 域表属 Phase 6，尚未建 ORM 模型，此处先返回 0。
    Phase 6 接入后补全真实聚合。admin.md §2.4 接受 MVP 多次 COUNT。
    """
    # TODO(Phase 6): 接入 practice_sessions/practice_attempts/recordings 表后补全
    return {
        "total_sessions": 0,
        "total_attempts": 0,
        "total_recordings": 0,
        "total_duration_seconds": 0,
    }


# ---------------------------------------------------------------------------
# 用户管理（admin.md §3）
# ---------------------------------------------------------------------------


async def list_users(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
    role: str | None = None,
) -> tuple[list[User], int]:
    """管理员用户列表（admin.md §3.1）。

    - keyword: ILIKE 匹配 email 或 profile.nickname（联合 profile 表）
    - status: active/disabled
    - role: user/admin（需 join roles 表）
    - 仅含未软删用户
    返回 (items, total)。
    """
    stmt = (
        select(User)
        .options(selectinload(User.role), selectinload(User.profile))
        .where(User.deleted_at.is_(None))
    )
    if keyword:
        kw = f"%{keyword}%"
        # email 直接匹配；nickname 需 join profiles
        stmt = stmt.outerjoin(UserProfile, UserProfile.user_id == User.id).where(
            or_(User.email.ilike(kw), UserProfile.nickname.ilike(kw))
        )
    if status:
        stmt = stmt.where(User.status == status)
    if role:
        stmt = stmt.join(Role, Role.id == User.role_id).where(Role.name == role)

    # 总数（用相同 where 但 count）
    count_stmt = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    if keyword:
        kw = f"%{keyword}%"
        count_stmt = count_stmt.outerjoin(UserProfile, UserProfile.user_id == User.id).where(
            or_(User.email.ilike(kw), UserProfile.nickname.ilike(kw))
        )
    if status:
        count_stmt = count_stmt.where(User.status == status)
    if role:
        count_stmt = count_stmt.join(Role, Role.id == User.role_id).where(Role.name == role)
    total = int((await db.execute(count_stmt)).scalar_one())

    # 分页
    stmt = stmt.order_by(User.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    result = await db.execute(stmt)
    items = list(result.scalars().unique().all())
    return items, total


async def get_user_by_id_admin(db: AsyncSession, user_id: int) -> User | None:
    """按 id 查用户（管理员视角，含软删用户，加载 role/profile）。"""
    stmt = (
        select(User)
        .options(selectinload(User.role), selectinload(User.profile))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 主题 CRUD（admin.md §4）
# ---------------------------------------------------------------------------


async def list_topics(
    db: AsyncSession, *, keyword: str | None = None
) -> list[SpeakingTopic]:
    """主题列表（未软删，按 sort_order, name 排序）。keyword ILIKE name。"""
    stmt = select(SpeakingTopic).where(SpeakingTopic.deleted_at.is_(None))
    if keyword:
        stmt = stmt.where(SpeakingTopic.name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(SpeakingTopic.sort_order, SpeakingTopic.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_topic_by_id(db: AsyncSession, topic_id: int) -> SpeakingTopic | None:
    """按 id 查主题（含软删，admin 视角）。"""
    stmt = select(SpeakingTopic).where(SpeakingTopic.id == topic_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_topic_by_name(
    db: AsyncSession, name: str
) -> SpeakingTopic | None:
    """按 name 查主题（含软删，用于唯一性检查 + 软删重名释放检测）。"""
    stmt = select(SpeakingTopic).where(SpeakingTopic.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def count_published_questions_by_topic(db: AsyncSession, topic_id: int) -> int:
    """该主题下 published 题目数（admin.md §4.1 question_count）。"""
    stmt = (
        select(func.count())
        .select_from(SpeakingQuestion)
        .where(
            SpeakingQuestion.topic_id == topic_id,
            SpeakingQuestion.status == "published",
        )
    )
    return int((await db.execute(stmt)).scalar_one())


# ---------------------------------------------------------------------------
# 标签 CRUD（admin.md §5）
# ---------------------------------------------------------------------------


async def list_tags(db: AsyncSession, *, keyword: str | None = None) -> list[Tag]:
    """标签列表（未软删，按 name 排序）。"""
    stmt = select(Tag).where(Tag.deleted_at.is_(None))
    if keyword:
        stmt = stmt.where(Tag.name.ilike(f"%{keyword}%"))
    stmt = stmt.order_by(Tag.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_tag_by_id(db: AsyncSession, tag_id: int) -> Tag | None:
    """按 id 查标签（含软删）。"""
    stmt = select(Tag).where(Tag.id == tag_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_tag_by_name(db: AsyncSession, name: str) -> Tag | None:
    """按 name 查标签（含软删，用于唯一性检查）。"""
    stmt = select(Tag).where(Tag.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def count_questions_by_tag(db: AsyncSession, tag_id: int) -> int:
    """引用该标签的题目数（admin.md §5.1 question_count，全状态）。"""
    stmt = (
        select(func.count())
        .select_from(QuestionTag)
        .where(QuestionTag.tag_id == tag_id)
    )
    return int((await db.execute(stmt)).scalar_one())


# ---------------------------------------------------------------------------
# 题目 CRUD（admin.md §6）
# ---------------------------------------------------------------------------


async def list_questions(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    part: int | None = None,
    topic_id: int | None = None,
    status: str | None = None,
    keyword: str | None = None,
    tag_id: int | None = None,
    difficulty: int | None = None,
) -> tuple[list[SpeakingQuestion], int]:
    """管理员题目列表（admin.md §6.1，含全部状态）。

    - keyword: ILIKE title 或 content
    - tag_id: 需 join question_tags
    返回 (items, total)，items 已加载 topic + tags 关系。
    """
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic), selectinload(SpeakingQuestion.tags))
    )
    count_stmt = select(func.count()).select_from(SpeakingQuestion)

    if part is not None:
        stmt = stmt.where(SpeakingQuestion.part == part)
        count_stmt = count_stmt.where(SpeakingQuestion.part == part)
    if topic_id is not None:
        stmt = stmt.where(SpeakingQuestion.topic_id == topic_id)
        count_stmt = count_stmt.where(SpeakingQuestion.topic_id == topic_id)
    if status is not None:
        stmt = stmt.where(SpeakingQuestion.status == status)
        count_stmt = count_stmt.where(SpeakingQuestion.status == status)
    if difficulty is not None:
        stmt = stmt.where(SpeakingQuestion.difficulty == difficulty)
        count_stmt = count_stmt.where(SpeakingQuestion.difficulty == difficulty)
    if keyword:
        kw = f"%{keyword}%"
        cond = or_(SpeakingQuestion.title.ilike(kw), SpeakingQuestion.content.ilike(kw))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if tag_id is not None:
        stmt = stmt.join(
            QuestionTag, QuestionTag.question_id == SpeakingQuestion.id
        ).where(QuestionTag.tag_id == tag_id)
        count_stmt = count_stmt.join(
            QuestionTag, QuestionTag.question_id == SpeakingQuestion.id
        ).where(QuestionTag.tag_id == tag_id)

    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = (
        stmt.order_by(SpeakingQuestion.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().unique().all())
    return items, total


async def get_question_by_id(
    db: AsyncSession, question_id: int
) -> SpeakingQuestion | None:
    """按 id 查题目（admin 视角，含 draft/disabled，加载 topic + tags）。"""
    stmt = (
        select(SpeakingQuestion)
        .options(selectinload(SpeakingQuestion.topic), selectinload(SpeakingQuestion.tags))
        .where(SpeakingQuestion.id == question_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_existing_tags(
    db: AsyncSession, tag_ids: list[int]
) -> list[Tag]:
    """批量查 tag_ids 对应的未软删标签（admin.md §6.2 tag_ids 校验 + 取 name）。"""
    if not tag_ids:
        return []
    stmt = select(Tag).where(Tag.id.in_(tag_ids), Tag.deleted_at.is_(None))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def replace_question_tags(
    db: AsyncSession, question_id: int, tag_ids: list[int]
) -> None:
    """替换题目标签（admin.md §6.4：DELETE 旧 question_tags + INSERT 新）。

    幂等：传入空列表则清空标签。事务内调用，由 service 层保证 flush。
    """
    await db.execute(
        delete(QuestionTag).where(QuestionTag.question_id == question_id)
    )
    for tid in tag_ids:
        db.add(QuestionTag(question_id=question_id, tag_id=tid))
    await db.flush()
