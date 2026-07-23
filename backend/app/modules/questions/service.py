"""Questions 模块（用户端）业务逻辑（system-architecture §3：service 层）。

对齐 questions.md §2/§3/§4/§5：
- 列表：published 可见 + 筛选 + 分页 + 排序 + 批量补 is_favorited/practice_count
- 详情：4001(不存在/draft)/4002(disabled) 分级
- 收藏：幂等 POST/DELETE，实际变更才写 activity_log
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.activity import UserActivityLog
from app.models.question import SpeakingQuestion
from app.models.user import User
from app.modules.questions import repository as repo
from app.modules.questions.schemas import (
    FavoriteResponse,
    QuestionDetail,
    QuestionListItem,
    TagRef,
    TopicRef,
)

# 题目状态（questions.md §3.4 分级用）
_STATUS_DRAFT = "draft"
_STATUS_DISABLED = "disabled"
_STATUS_PUBLISHED = "published"


def _build_topic_ref(question: SpeakingQuestion) -> TopicRef:
    """构造 TopicRef（questions.md §7.1）。topic 关系已加载。"""
    return TopicRef(id=str(question.topic.id), name=question.topic.name)


def _build_list_item(
    question: SpeakingQuestion,
    *,
    is_favorited: bool,
    practice_count: int,
) -> QuestionListItem:
    """构造 QuestionListItem（§2.2）。"""
    return QuestionListItem(
        id=str(question.id),
        part=question.part,
        title=question.title,
        topic=_build_topic_ref(question),
        difficulty=question.difficulty,
        is_favorited=is_favorited,
        practice_count=practice_count,
        created_at=question.created_at,
    )


def _build_detail(
    question: SpeakingQuestion,
    *,
    is_favorited: bool,
    practice_count: int,
) -> QuestionDetail:
    """构造 QuestionDetail（§3.2，不含 created_by/status/updated_at）。"""
    return QuestionDetail(
        id=str(question.id),
        part=question.part,
        title=question.title,
        topic=_build_topic_ref(question),
        difficulty=question.difficulty,
        is_favorited=is_favorited,
        practice_count=practice_count,
        created_at=question.created_at,
        content=question.content,
        cue_card=question.cue_card,
        tags=[TagRef(id=str(t.id), name=t.name) for t in question.tags],
        source_type=question.source_type,
        source_name=question.source_name,
    )


# ---------------------------------------------------------------------------
# 列表（questions.md §2）
# ---------------------------------------------------------------------------


async def list_questions(
    db: AsyncSession,
    *,
    current_user: User,
    page: int,
    page_size: int,
    part: int | None = None,
    topic_id: int | None = None,
    difficulty: int | None = None,
    keyword: str | None = None,
    tag_id: int | None = None,
    is_favorited: bool | None = None,
    sort: str = "newest",
) -> dict:
    """用户端题目列表（questions.md §2）。

    返回 {items, total, page, page_size, total_pages}。
    topic_id/tag_id 指向不存在资源时返回空列表（§2.3，不报错）。
    """
    items, total = await repo.list_published_questions(
        db,
        page=page,
        page_size=page_size,
        part=part,
        topic_id=topic_id,
        difficulty=difficulty,
        keyword=keyword,
        tag_id=tag_id,
        user_id=current_user.id,
        is_favorited=is_favorited,
        sort=sort,
    )

    # 批量补 is_favorited + practice_count（§2.4 step 7/8，避免 N+1）
    qids = [q.id for q in items]
    favorited_ids = await repo.batch_favorited_question_ids(db, current_user.id, qids)
    practice_counts = await repo.batch_practice_counts(db, qids)

    list_items = [
        _build_list_item(
            q,
            is_favorited=q.id in favorited_ids,
            practice_count=practice_counts.get(q.id, 0),
        )
        for q in items
    ]

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": [it.model_dump(mode="json") for it in list_items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# 详情（questions.md §3）
# ---------------------------------------------------------------------------


async def get_question_detail(
    db: AsyncSession, question_id: int, *, current_user: User
) -> dict:
    """题目详情（questions.md §3.4，4001/4002 分级）。

    - 不存在 → 4001/404
    - draft → 4001/404（草稿等同不存在，不暴露存在性）
    - disabled → 4002/400（明确"已下架"）
    - published → 返回详情
    """
    question = await repo.get_question_with_status(db, question_id)
    if question is None or question.status == _STATUS_DRAFT:
        # questions.md §3.3/§3.4：draft 等同不存在（防探测）
        raise AppError(code=4001, message="题目不存在", http_status=404)
    if question.status == _STATUS_DISABLED:
        # questions.md §3.3：disabled 明确"已下架"，区分于 4001
        raise AppError(code=4002, message="该题目已下架", http_status=400)

    favorited_ids = await repo.batch_favorited_question_ids(
        db, current_user.id, [question.id]
    )
    practice_counts = await repo.batch_practice_counts(db, [question.id])
    detail = _build_detail(
        question,
        is_favorited=question.id in favorited_ids,
        practice_count=practice_counts.get(question.id, 0),
    )
    return detail.model_dump(mode="json")


# ---------------------------------------------------------------------------
# 收藏（questions.md §4/§5）
# ---------------------------------------------------------------------------


async def favorite_question(
    db: AsyncSession, question_id: int, *, current_user: User
) -> dict:
    """收藏题目（questions.md §4，幂等）。

    - 非 published（draft/disabled）→ 4001/404（防探测，§4.3/§6.1）
    - ON CONFLICT DO NOTHING，重复收藏返回 is_favorited=true（§4.2）
    - 实际新增才写 activity_log(favorite_added)（§4.4/§6.5）
    """
    question = await repo.get_published_question_by_id(db, question_id)
    if question is None:
        # 非 published 等同不存在（防探测，不区分 disabled/draft）
        raise AppError(code=4001, message="题目不存在", http_status=404)

    added = await repo.add_favorite(db, current_user.id, question_id)
    if added:
        log = UserActivityLog(
            user_id=current_user.id,
            action="favorite_added",
            entity_type="question",
            entity_id=question_id,
        )
        db.add(log)
        await db.flush()

    resp = FavoriteResponse(question_id=str(question_id), is_favorited=True)
    return resp.model_dump(mode="json")


async def unfavorite_question(
    db: AsyncSession, question_id: int, *, current_user: User
) -> dict:
    """取消收藏（questions.md §5，幂等）。

    - 不校验题目状态（§5.3：无论题目是否存在/已收藏，均返回 is_favorited=false）
    - 实际删除才写 activity_log(favorite_removed)（§5.4/§6.5）
    """
    removed = await repo.remove_favorite(db, current_user.id, question_id)
    if removed:
        log = UserActivityLog(
            user_id=current_user.id,
            action="favorite_removed",
            entity_type="question",
            entity_id=question_id,
        )
        db.add(log)
        await db.flush()

    resp = FavoriteResponse(question_id=str(question_id), is_favorited=False)
    return resp.model_dump(mode="json")
