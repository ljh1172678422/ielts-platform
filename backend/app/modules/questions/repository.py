"""Questions 模块（用户端）SQLAlchemy 查询封装（system-architecture §3）。

对齐 questions.md §2.4/§3.4/§4.4/§5.4：
- 用户端仅查 status='published'（ADR-010），draft/disabled 对用户端不可见
- 列表筛选：part / topic_id / difficulty / keyword(ILIKE title+content) / tag_id(EXISTS) / is_favorited(EXISTS)
- 排序：newest(created_at DESC) / popular(practice_count DESC, created_at DESC)
- 批量查询避免 N+1：当前页 items 的 is_favorited + practice_count
- 收藏幂等：ON CONFLICT DO NOTHING（INSERT）/ 无影响行也成功（DELETE）
"""
from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite import Favorite
from app.models.practice import PracticeSessionQuestion
from app.models.question import QuestionTag, SpeakingQuestion

# 用户端可见状态：仅 published（questions.md §1.4 / ADR-010）
PUBLISHED = "published"


# ---------------------------------------------------------------------------
# 列表（questions.md §2.4）
# ---------------------------------------------------------------------------


def _apply_filters(
    stmt,
    *,
    part: int | None,
    topic_id: int | None,
    difficulty: int | None,
    keyword: str | None,
    tag_id: int | None,
    user_id: int | None,
    is_favorited: bool | None,
):
    """叠加筛选条件到 stmt（列表与 count 共用，保证总数与结果集一致）。"""
    # 基础过滤：仅 published（questions.md §2.4 step 1）
    stmt = stmt.where(SpeakingQuestion.status == PUBLISHED)

    if part is not None:
        stmt = stmt.where(SpeakingQuestion.part == part)
    if topic_id is not None:
        stmt = stmt.where(SpeakingQuestion.topic_id == topic_id)
    if difficulty is not None:
        stmt = stmt.where(SpeakingQuestion.difficulty == difficulty)
    if keyword:
        kw = f"%{keyword}%"
        stmt = stmt.where(
            or_(SpeakingQuestion.title.ilike(kw), SpeakingQuestion.content.ilike(kw))
        )
    if tag_id is not None:
        # questions.md §2.4 step 3：EXISTS 子查询，避免 join 改变行数
        tag_exists = (
            select(1)
            .select_from(QuestionTag)
            .where(
                QuestionTag.question_id == SpeakingQuestion.id,
                QuestionTag.tag_id == tag_id,
            )
            .exists()
        )
        stmt = stmt.where(tag_exists)
    if is_favorited is True and user_id is not None:
        # questions.md §2.4 step 4：仅看我收藏的
        fav_exists = (
            select(1)
            .select_from(Favorite)
            .where(
                Favorite.question_id == SpeakingQuestion.id,
                Favorite.user_id == user_id,
            )
            .exists()
        )
        stmt = stmt.where(fav_exists)
    return stmt


async def list_published_questions(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    part: int | None = None,
    topic_id: int | None = None,
    difficulty: int | None = None,
    keyword: str | None = None,
    tag_id: int | None = None,
    user_id: int | None = None,
    is_favorited: bool | None = None,
    sort: str = "newest",
) -> tuple[list[SpeakingQuestion], int]:
    """用户端题目列表（questions.md §2.4）。

    返回 (items, total)，items 已加载 topic（列表项不含 tags，减少负载）。
    topic_id/tag_id 指向不存在资源时不报错，返回空列表（§2.3）。
    """
    stmt = select(SpeakingQuestion).options(selectinload(SpeakingQuestion.topic))
    stmt = _apply_filters(
        stmt,
        part=part,
        topic_id=topic_id,
        difficulty=difficulty,
        keyword=keyword,
        tag_id=tag_id,
        user_id=user_id,
        is_favorited=is_favorited,
    )

    # 总数（同 where，不含排序/分页）
    count_stmt = select(func.count()).select_from(SpeakingQuestion)
    count_stmt = _apply_filters(
        count_stmt,
        part=part,
        topic_id=topic_id,
        difficulty=difficulty,
        keyword=keyword,
        tag_id=tag_id,
        user_id=user_id,
        is_favorited=is_favorited,
    )
    total = int((await db.execute(count_stmt)).scalar_one())

    # 排序（questions.md §2.4 step 5）
    if sort == "popular":
        # practice_count 标量子查询（LEFT JOIN 语义，无练习记录视为 0）
        practice_count_expr = (
            select(func.count())
            .select_from(PracticeSessionQuestion)
            .where(PracticeSessionQuestion.question_id == SpeakingQuestion.id)
            .scalar_subquery()
        )
        stmt = stmt.order_by(
            func.coalesce(practice_count_expr, 0).desc(),
            SpeakingQuestion.created_at.desc(),
        )
    else:
        # newest（默认）
        stmt = stmt.order_by(SpeakingQuestion.created_at.desc())

    # 分页（§2.4 step 6）
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    result = await db.execute(stmt)
    items = list(result.scalars().unique().all())
    return items, total


# ---------------------------------------------------------------------------
# 详情（questions.md §3.4）
# ---------------------------------------------------------------------------


async def get_question_with_status(
    db: AsyncSession, question_id: int
) -> SpeakingQuestion | None:
    """按 id 查题目（含 draft/disabled，加载 topic + tags），供 service 做
    4001/4002 分级判断（questions.md §3.4 step 1）。

    用户端列表/详情的 published 过滤由 service 层根据 status 判断，
    本函数返回原始 status 供分级（draft→4001，disabled→4002）。
    """
    stmt = (
        select(SpeakingQuestion)
        .options(
            selectinload(SpeakingQuestion.topic), selectinload(SpeakingQuestion.tags)
        )
        .where(SpeakingQuestion.id == question_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_published_question_by_id(
    db: AsyncSession, question_id: int
) -> SpeakingQuestion | None:
    """按 id 查 published 题目（收藏接口校验用，questions.md §4.4 step 1）。

    非 published（draft/disabled）对用户端等同不存在 → 返回 None → service 抛 4001
    （防探测，§6.1）。
    """
    stmt = (
        select(SpeakingQuestion)
        .where(
            SpeakingQuestion.id == question_id,
            SpeakingQuestion.status == PUBLISHED,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 批量查询（避免 N+1，questions.md §2.4 step 7/8）
# ---------------------------------------------------------------------------


async def batch_favorited_question_ids(
    db: AsyncSession, user_id: int, question_ids: list[int]
) -> set[int]:
    """批量查当前用户已收藏的 question_id 集合（§2.4 step 7）。"""
    if not question_ids:
        return set()
    stmt = select(Favorite.question_id).where(
        Favorite.user_id == user_id,
        Favorite.question_id.in_(question_ids),
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def batch_practice_counts(
    db: AsyncSession, question_ids: list[int]
) -> dict[int, int]:
    """批量聚合 practice_count（§2.4 step 8，practice_session_questions 引用数）。"""
    if not question_ids:
        return {}
    stmt = (
        select(PracticeSessionQuestion.question_id, func.count())
        .where(PracticeSessionQuestion.question_id.in_(question_ids))
        .group_by(PracticeSessionQuestion.question_id)
    )
    result = await db.execute(stmt)
    return {qid: int(cnt) for qid, cnt in result.all()}


# ---------------------------------------------------------------------------
# 收藏（questions.md §4.4/§5.4）
# ---------------------------------------------------------------------------


async def add_favorite(db: AsyncSession, user_id: int, question_id: int) -> bool:
    """幂等收藏（§4.4 step 2）：ON CONFLICT DO NOTHING。

    返回 True 表示本次实际新增，False 表示已存在（幂等命中）。
    service 层据此决定是否写 activity_log(favorite_added)。
    """
    stmt = (
        pg_insert(Favorite)
        .values(user_id=user_id, question_id=question_id)
        .on_conflict_do_nothing(index_elements=["user_id", "question_id"])
    )
    result = await db.execute(stmt)
    # rowcount：受影响行数（1=新增，0=冲突未插入）
    return (result.rowcount or 0) > 0


async def remove_favorite(db: AsyncSession, user_id: int, question_id: int) -> bool:
    """幂等取消收藏（§5.4 step 1）：DELETE，无影响行也视为成功。

    返回 True 表示本次实际删除，False 表示原本未收藏（幂等）。
    service 层据此决定是否写 activity_log(favorite_removed)。
    """
    stmt = delete(Favorite).where(
        Favorite.user_id == user_id,
        Favorite.question_id == question_id,
    )
    result = await db.execute(stmt)
    return (result.rowcount or 0) > 0
