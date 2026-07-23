"""Admin 模块业务逻辑（system-architecture §3：service 层）。

Phase 5.1 Dashboard：聚合各表统计返回概览。
后续 5.2-5.5 在本文件追加用户/主题/标签/题目 service。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.activity import UserActivityLog
from app.models.question import QuestionTag, SpeakingQuestion, SpeakingTopic, Tag
from app.models.user import User
from app.modules.admin import repository as repo
from app.modules.admin.schemas import (
    AdminQuestionDetail,
    AdminQuestionListItem,
    AdminTagItem,
    AdminTopicItem,
    AdminUserListItem,
    DashboardData,
    DashboardPractice,
    DashboardQuestions,
    DashboardTags,
    DashboardTopics,
    DashboardUsers,
    QuestionUpsertRequest,
    TagRef,
    TagUpsertRequest,
    TopicRef,
    TopicUpsertRequest,
)


async def get_dashboard(db: AsyncSession) -> DashboardData:
    """全局统计概览（admin.md §2）。

    MVP 接受多次 COUNT 查询（数据量小，admin.md §2.4）。
    """
    users_total = await repo.count_users_total(db)
    active_today = await repo.count_users_active_today(db)
    new_this_week = await repo.count_users_new_this_week(db)

    q_counts = await repo.count_questions_by_status(db)

    practice = await repo.count_practice_stats(db)

    topics_total = await repo.count_topics_total(db)
    tags_total = await repo.count_tags_total(db)

    return DashboardData(
        users=DashboardUsers(
            total=users_total,
            active_today=active_today,
            new_this_week=new_this_week,
        ),
        questions=DashboardQuestions(
            total=q_counts["total"],
            published=q_counts["published"],
            draft=q_counts["draft"],
            disabled=q_counts["disabled"],
        ),
        practice=DashboardPractice(**practice),
        topics=DashboardTopics(total=topics_total),
        tags=DashboardTags(total=tags_total),
    )


# ---------------------------------------------------------------------------
# 用户管理（admin.md §3）
# ---------------------------------------------------------------------------


def _build_user_list_item(user: User) -> AdminUserListItem:
    """从 ORM User 构造 AdminUserListItem（admin.md §3.1，id 转 str ADR-025）。"""
    nickname = user.profile.nickname if user.profile else None
    return AdminUserListItem(
        id=str(user.id),
        email=user.email,
        role=user.role.name,
        status=user.status,
        nickname=nickname,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


async def list_users(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    keyword: str | None = None,
    status: str | None = None,
    role: str | None = None,
) -> dict:
    """管理员用户列表（admin.md §3.1）。

    返回 {items, total, page, page_size, total_pages}。
    """
    items, total = await repo.list_users(
        db, page=page, page_size=page_size, keyword=keyword, status=status, role=role
    )
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": [_build_user_list_item(u).model_dump(mode="json") for u in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def update_user_status(
    db: AsyncSession, *, target_id: int, new_status: str, current_user: User
) -> dict:
    """启用/禁用用户（admin.md §3.2）。

    业务校验：
    1. target 不存在 → 1002/404
    2. target.id == current.id → 8006/400（防自锁）
    3. target.role == 'admin' → 8007/400（防管理员互操作）
    4. UPDATE status + 写 activity_log(user_status_changed)
    返回更新后的用户摘要（同列表项结构）。
    """
    target = await repo.get_user_by_id_admin(db, target_id)
    if target is None:
        raise AppError(
            code=1002,
            message="用户不存在",
            http_status=404,
        )

    if target.id == current_user.id:
        raise AppError(
            code=8006,
            message="管理员不可操作自己",
            http_status=400,
        )

    if target.role.name == "admin":
        raise AppError(
            code=8007,
            message="管理员不可操作其他管理员",
            http_status=400,
        )

    old_status = target.status
    target.status = new_status

    log = UserActivityLog(
        user_id=current_user.id,
        action="user_status_changed",
        entity_type="user",
        entity_id=target.id,
        metadata_={"old": old_status, "new": new_status},
    )
    db.add(log)
    await db.flush()

    return _build_user_list_item(target).model_dump(mode="json")


# ---------------------------------------------------------------------------
# 主题 CRUD（admin.md §4）
# ---------------------------------------------------------------------------

OTHER_TOPIC_NAME = "Other"  # 系统保留主题名（PROJECT_SPEC §12.3）


def _is_system_topic(topic: SpeakingTopic) -> bool:
    """是否系统保留主题（name == 'Other'，PROJECT_SPEC §12.3）。"""
    return topic.name == OTHER_TOPIC_NAME


async def _build_topic_item(
    db: AsyncSession, topic: SpeakingTopic
) -> AdminTopicItem:
    """构造 AdminTopicItem（含 question_count + is_system + slug 派生）。

    DB 无 slug 列，MVP slug = name（admin.md §4.1 响应有 slug 但 schema 无列）。
    """
    qcount = await repo.count_published_questions_by_topic(db, topic.id)
    return AdminTopicItem(
        id=str(topic.id),
        name=topic.name,
        slug=topic.name,  # MVP 派生：slug = name
        description=topic.description,
        question_count=qcount,
        is_system=_is_system_topic(topic),
        created_at=topic.created_at,
    )


async def list_topics(db: AsyncSession, *, keyword: str | None = None) -> dict:
    """主题列表（admin.md §4.1，非分页）。"""
    topics = await repo.list_topics(db, keyword=keyword)
    items = [await _build_topic_item(db, t) for t in topics]
    return {"items": [it.model_dump(mode="json") for it in items]}


async def create_topic(
    db: AsyncSession, req: TopicUpsertRequest, *, current_user: User
) -> dict:
    """创建主题（admin.md §4.2）。

    - name 唯一冲突 → 1004/409（含软删重名检测）
    - 不允许创建名为 'Other' 的主题（系统保留）→ 8001/400
    """
    if req.name == OTHER_TOPIC_NAME:
        raise AppError(
            code=8001,
            message=f"'{OTHER_TOPIC_NAME}' 为系统保留主题名，不可创建",
            http_status=400,
        )

    existing = await repo.get_topic_by_name(db, req.name)
    if existing is not None and existing.deleted_at is None:
        raise AppError(
            code=1004,
            message="主题名称已存在",
            http_status=409,
            details=[{"field": "name", "message": "name already in use"}],
        )

    topic = SpeakingTopic(name=req.name, description=req.description)
    db.add(topic)
    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="topic_created",
        entity_type="topic",
        entity_id=topic.id,
    )
    db.add(log)
    await db.flush()

    item = await _build_topic_item(db, topic)
    return item.model_dump(mode="json")


async def update_topic(
    db: AsyncSession, topic_id: int, req: TopicUpsertRequest, *, current_user: User
) -> dict:
    """更新主题（admin.md §4.3，全量替换）。

    - 主题不存在 → 4003/404
    - Other 主题改 name → 8001/400（仅允许改 description）
    - name 与其他主题冲突 → 1004/409
    """
    topic = await repo.get_topic_by_id(db, topic_id)
    if topic is None or topic.deleted_at is not None:
        raise AppError(code=4003, message="主题不存在", http_status=404)

    is_system = _is_system_topic(topic)
    if is_system and req.name != OTHER_TOPIC_NAME:
        raise AppError(
            code=8001,
            message="系统保留主题不可修改名称",
            http_status=400,
        )

    # name 变更时检查唯一性（排除自身 + 软删项不算）
    if req.name != topic.name:
        existing = await repo.get_topic_by_name(db, req.name)
        if existing is not None and existing.id != topic.id and existing.deleted_at is None:
            raise AppError(
                code=1004,
                message="主题名称已存在",
                http_status=409,
            )
        topic.name = req.name

    topic.description = req.description
    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="topic_updated",
        entity_type="topic",
        entity_id=topic.id,
    )
    db.add(log)
    await db.flush()

    item = await _build_topic_item(db, topic)
    return item.model_dump(mode="json")


async def delete_topic(
    db: AsyncSession, topic_id: int, *, current_user: User
) -> None:
    """软删主题（admin.md §4.4）。

    - 不存在 → 4003/404
    - Other 主题 → 8001/400
    - 仍有 published 题目 → 8002/400
    """
    topic = await repo.get_topic_by_id(db, topic_id)
    if topic is None or topic.deleted_at is not None:
        raise AppError(code=4003, message="主题不存在", http_status=404)

    if _is_system_topic(topic):
        raise AppError(
            code=8001,
            message="系统保留主题不可删除",
            http_status=400,
        )

    qcount = await repo.count_published_questions_by_topic(db, topic.id)
    if qcount > 0:
        raise AppError(
            code=8002,
            message="主题下仍有已发布题目，不可删除",
            http_status=400,
        )

    topic.deleted_at = datetime.now(UTC)
    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="topic_deleted",
        entity_type="topic",
        entity_id=topic.id,
    )
    db.add(log)
    await db.flush()


# ---------------------------------------------------------------------------
# 标签 CRUD（admin.md §5）
# ---------------------------------------------------------------------------


async def _build_tag_item(db: AsyncSession, tag: Tag) -> AdminTagItem:
    """构造 AdminTagItem（含 question_count + slug 派生）。"""
    qcount = await repo.count_questions_by_tag(db, tag.id)
    return AdminTagItem(
        id=str(tag.id),
        name=tag.name,
        slug=tag.name,  # MVP 派生
        question_count=qcount,
        created_at=tag.created_at,
    )


async def list_tags(db: AsyncSession, *, keyword: str | None = None) -> dict:
    """标签列表（admin.md §5.1，非分页）。"""
    tags = await repo.list_tags(db, keyword=keyword)
    items = [await _build_tag_item(db, t) for t in tags]
    return {"items": [it.model_dump(mode="json") for it in items]}


async def create_tag(
    db: AsyncSession, req: TagUpsertRequest, *, current_user: User
) -> dict:
    """创建标签（admin.md §5.2）。name 唯一冲突 → 1004/409。"""
    existing = await repo.get_tag_by_name(db, req.name)
    if existing is not None and existing.deleted_at is None:
        raise AppError(
            code=1004,
            message="标签名称已存在",
            http_status=409,
        )

    tag = Tag(name=req.name)
    db.add(tag)
    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="tag_created",
        entity_type="tag",
        entity_id=tag.id,
    )
    db.add(log)
    await db.flush()

    item = await _build_tag_item(db, tag)
    return item.model_dump(mode="json")


async def update_tag(
    db: AsyncSession, tag_id: int, req: TagUpsertRequest, *, current_user: User
) -> dict:
    """更新标签（admin.md §5.3）。不存在 → 4004/404，name 冲突 → 1004/409。"""
    tag = await repo.get_tag_by_id(db, tag_id)
    if tag is None or tag.deleted_at is not None:
        raise AppError(code=4004, message="标签不存在", http_status=404)

    if req.name != tag.name:
        existing = await repo.get_tag_by_name(db, req.name)
        if existing is not None and existing.id != tag.id and existing.deleted_at is None:
            raise AppError(
                code=1004,
                message="标签名称已存在",
                http_status=409,
            )
        tag.name = req.name

    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="tag_updated",
        entity_type="tag",
        entity_id=tag.id,
    )
    db.add(log)
    await db.flush()

    item = await _build_tag_item(db, tag)
    return item.model_dump(mode="json")


async def delete_tag(
    db: AsyncSession, tag_id: int, *, current_user: User
) -> None:
    """软删标签（admin.md §5.4）。

    - 不存在 → 4004/404
    - 仍被题目引用 → 8002/400（需先解除 question_tags 关联）
    """
    tag = await repo.get_tag_by_id(db, tag_id)
    if tag is None or tag.deleted_at is not None:
        raise AppError(code=4004, message="标签不存在", http_status=404)

    qcount = await repo.count_questions_by_tag(db, tag.id)
    if qcount > 0:
        raise AppError(
            code=8002,
            message="标签仍被题目引用，需先解除关联",
            http_status=400,
        )

    tag.deleted_at = datetime.now(UTC)
    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="tag_deleted",
        entity_type="tag",
        entity_id=tag.id,
    )
    db.add(log)
    await db.flush()


# ---------------------------------------------------------------------------
# 题目 CRUD（admin.md §6）
# ---------------------------------------------------------------------------

# practice_count：Phase 5 MVP 占位 0（practice_session_questions 表属 Phase 7，
# 与 dashboard practice 统计一致策略），Phase 7 接入后补全真实引用计数。
_QUESTION_PRACTICE_COUNT_PLACEHOLDER = 0


def _to_int_id(value: str, field: str) -> int:
    """字符串 id → int，非法 → 1001/422（admin.md §6 topic_id/tag_ids 字符串化）。"""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": field, "message": f"invalid id: {value}"}],
        ) from exc


def _question_common_fields(question: SpeakingQuestion) -> dict:
    """构造 AdminQuestionListItem/Detail 共用字段（关系需已加载/attach）。

    topic 必填（ADR-019 topic_id NOT NULL）；tags 可空。
    """
    topic = question.topic
    return {
        "id": str(question.id),
        "part": question.part,
        "title": question.title,
        "topic": TopicRef(id=str(topic.id), name=topic.name),
        "tags": [TagRef(id=str(t.id), name=t.name) for t in (question.tags or [])],
        "difficulty": question.difficulty,
        "status": question.status,
        "source_type": question.source_type,
        "source_name": question.source_name,
        "practice_count": _QUESTION_PRACTICE_COUNT_PLACEHOLDER,
        "created_by": str(question.created_by) if question.created_by else None,
        "created_at": question.created_at,
        "updated_at": question.updated_at,
    }


def _build_question_list_item(question: SpeakingQuestion) -> AdminQuestionListItem:
    return AdminQuestionListItem(**_question_common_fields(question))


def _build_question_detail(question: SpeakingQuestion) -> AdminQuestionDetail:
    return AdminQuestionDetail(
        **_question_common_fields(question),
        content=question.content,
        cue_card=question.cue_card,
    )


async def _validate_topic_and_tags(
    db: AsyncSession, req: QuestionUpsertRequest
) -> tuple[SpeakingTopic, list[Tag]]:
    """校验 topic_id 存在（未软删）+ tag_ids 全部存在。

    - topic_id 不存在/已软删 → 4003/404
    - tag_ids 中某 id 不存在 → 4004/404
    返回 (topic, ordered_tags)，ordered_tags 按 req.tag_ids 顺序。
    """
    topic_int_id = _to_int_id(req.topic_id, "topic_id")
    topic = await repo.get_topic_by_id(db, topic_int_id)
    if topic is None or topic.deleted_at is not None:
        raise AppError(code=4003, message="主题不存在", http_status=404)

    tag_int_ids = [_to_int_id(t, "tag_ids") for t in req.tag_ids]
    existing_tags: list[Tag] = []
    if tag_int_ids:
        existing_tags = await repo.get_existing_tags(db, tag_int_ids)
        existing_ids = {t.id for t in existing_tags}
        missing = set(tag_int_ids) - existing_ids
        if missing:
            raise AppError(code=4004, message="标签不存在", http_status=404)

    # 按 req.tag_ids 顺序排列（去重保留首次出现）
    tag_map = {t.id: t for t in existing_tags}
    ordered_tags: list[Tag] = []
    seen: set[int] = set()
    for tid in tag_int_ids:
        if tid in tag_map and tid not in seen:
            ordered_tags.append(tag_map[tid])
            seen.add(tid)
    return topic, ordered_tags


async def list_questions(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    part: int | None = None,
    topic_id: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    tag_id: str | None = None,
    difficulty: int | None = None,
) -> dict:
    """管理员题目列表（admin.md §6.1，含全部状态）。"""
    topic_int = _to_int_id(topic_id, "topic_id") if topic_id else None
    tag_int = _to_int_id(tag_id, "tag_id") if tag_id else None

    items, total = await repo.list_questions(
        db,
        page=page,
        page_size=page_size,
        part=part,
        topic_id=topic_int,
        status=status,
        keyword=keyword,
        tag_id=tag_int,
        difficulty=difficulty,
    )
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        "items": [_build_question_list_item(q).model_dump(mode="json") for q in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_question_detail(db: AsyncSession, question_id: int) -> dict:
    """题目详情（admin.md §6.3，含 draft/disabled）。

    管理员可见全部状态，不返回 4002。
    - 题目不存在 → 4001/404
    """
    question = await repo.get_question_by_id(db, question_id)
    if question is None:
        raise AppError(code=4001, message="题目不存在", http_status=404)
    return _build_question_detail(question).model_dump(mode="json")


async def create_question(
    db: AsyncSession, req: QuestionUpsertRequest, *, current_user: User
) -> dict:
    """创建题目（admin.md §6.2）。

    - topic_id 不存在 → 4003/404
    - tag_ids 中某 id 不存在 → 4004/404
    - created_by 自动填当前管理员 id（不接受前端传入）
    - status 默认 draft
    返回新建题目详情（同 §6.3）。
    """
    topic, ordered_tags = await _validate_topic_and_tags(db, req)

    question = SpeakingQuestion(
        part=req.part,
        topic_id=topic.id,
        title=req.title,
        content=req.content,
        cue_card=req.cue_card,
        difficulty=req.difficulty,
        status=req.status or "draft",
        source_type=req.source_type,
        source_name=req.source_name,
        created_by=current_user.id,
    )
    db.add(question)
    await db.flush()  # 取 question.id

    for tag in ordered_tags:
        db.add(QuestionTag(question_id=question.id, tag_id=tag.id))

    log = UserActivityLog(
        user_id=current_user.id,
        action="question_created",
        entity_type="question",
        entity_id=question.id,
    )
    db.add(log)
    await db.flush()

    # 手动 attach 关系（刚 flush 未刷新 selectinload 关系）
    question.topic = topic
    question.tags = ordered_tags
    return _build_question_detail(question).model_dump(mode="json")


async def update_question(
    db: AsyncSession,
    question_id: int,
    req: QuestionUpsertRequest,
    *,
    current_user: User,
) -> dict:
    """更新题目（admin.md §6.4，全量替换）。

    - 题目不存在 → 4001/404
    - topic_id 不存在 → 4003/404
    - tag_ids 中某 id 不存在 → 4004/404
    - tag_ids 变化：DELETE 旧 question_tags + INSERT 新（事务内）
    - status 可选：传则改，不传则保持原值
    - 不影响历史 session_questions.snapshot（ADR-016）
    """
    question = await repo.get_question_by_id(db, question_id)
    if question is None:
        raise AppError(code=4001, message="题目不存在", http_status=404)

    topic, ordered_tags = await _validate_topic_and_tags(db, req)

    # 全量替换字段
    question.part = req.part
    question.topic_id = topic.id
    question.title = req.title
    question.content = req.content
    question.cue_card = req.cue_card
    question.difficulty = req.difficulty
    question.source_type = req.source_type
    question.source_name = req.source_name
    if req.status is not None:
        question.status = req.status
    await db.flush()

    # 替换 question_tags（DELETE 旧 + INSERT 新）
    await repo.replace_question_tags(db, question.id, [t.id for t in ordered_tags])

    log = UserActivityLog(
        user_id=current_user.id,
        action="question_updated",
        entity_type="question",
        entity_id=question.id,
    )
    db.add(log)
    await db.flush()

    # 关系已过期（replace 后 question.tags 仍是旧值），手动 attach 新关系
    question.topic = topic
    question.tags = ordered_tags
    return _build_question_detail(question).model_dump(mode="json")


async def update_question_status(
    db: AsyncSession,
    question_id: int,
    new_status: str,
    *,
    current_user: User,
) -> dict:
    """切换题目状态（admin.md §6.5）。

    MVP 不限制状态转换方向（管理员全权），仅记录 activity_log。
    - 题目不存在 → 4001/404
    返回更新后的题目详情。
    """
    question = await repo.get_question_by_id(db, question_id)
    if question is None:
        raise AppError(code=4001, message="题目不存在", http_status=404)

    old_status = question.status
    question.status = new_status
    await db.flush()

    log = UserActivityLog(
        user_id=current_user.id,
        action="question_status_changed",
        entity_type="question",
        entity_id=question.id,
        metadata_={"old": old_status, "new": new_status},
    )
    db.add(log)
    await db.flush()

    # get_question_by_id 已加载 topic + tags 关系
    return _build_question_detail(question).model_dump(mode="json")
