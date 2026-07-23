"""Admin 模块路由（admin.md §1.2）。

所有 /admin/* 需 Bearer token + role='admin'（admin.md §1.1）。
Phase 5.1：Dashboard。后续 5.2-5.5 追加用户/主题/标签/题目路由。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.exceptions import success
from app.models.user import User
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import (
    QuestionUpsertRequest,
    TagUpsertRequest,
    TopicUpsertRequest,
    UpdateQuestionStatusRequest,
    UpdateUserStatusRequest,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    # 所有 admin 接口都需管理员鉴权（admin.md §1.1）
    dependencies=[Depends(require_admin)],
)


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """全局统计概览（admin.md §2）。"""
    data = await admin_service.get_dashboard(db)
    return success(data.model_dump())


# ---------------------------------------------------------------------------
# 用户管理（admin.md §3）
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(active|disabled)$"),
    role: str | None = Query(default=None, pattern="^(user|admin)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """用户列表（分页+筛选，admin.md §3.1）。"""
    data = await admin_service.list_users(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        role=role,
    )
    return success(data)


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    req: UpdateUserStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """启用/禁用用户（admin.md §3.2，8006/8007 防自锁/防互操作）。"""
    data = await admin_service.update_user_status(
        db,
        target_id=user_id,
        new_status=req.status,
        current_user=current_user,
    )
    return success(data)


# ---------------------------------------------------------------------------
# 主题 CRUD（admin.md §4）
# ---------------------------------------------------------------------------


@router.get("/topics")
async def list_topics(
    keyword: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """主题列表（admin.md §4.1）。"""
    data = await admin_service.list_topics(db, keyword=keyword)
    return success(data)


@router.post("/topics")
async def create_topic(
    req: TopicUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """创建主题（admin.md §4.2）。"""
    data = await admin_service.create_topic(db, req, current_user=current_user)
    return success(data)


@router.put("/topics/{topic_id}")
async def update_topic(
    topic_id: int,
    req: TopicUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """更新主题（admin.md §4.3，8001 Other 保护）。"""
    data = await admin_service.update_topic(db, topic_id, req, current_user=current_user)
    return success(data)


@router.delete("/topics/{topic_id}")
async def delete_topic(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """软删主题（admin.md §4.4，8001 Other 保护 + 8002 引用检查）。"""
    await admin_service.delete_topic(db, topic_id, current_user=current_user)
    return success(None)


# ---------------------------------------------------------------------------
# 标签 CRUD（admin.md §5）
# ---------------------------------------------------------------------------


@router.get("/tags")
async def list_tags(
    keyword: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """标签列表（admin.md §5.1）。"""
    data = await admin_service.list_tags(db, keyword=keyword)
    return success(data)


@router.post("/tags")
async def create_tag(
    req: TagUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """创建标签（admin.md §5.2）。"""
    data = await admin_service.create_tag(db, req, current_user=current_user)
    return success(data)


@router.put("/tags/{tag_id}")
async def update_tag(
    tag_id: int,
    req: TagUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """更新标签（admin.md §5.3）。"""
    data = await admin_service.update_tag(db, tag_id, req, current_user=current_user)
    return success(data)


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """软删标签（admin.md §5.4，8002 引用检查）。"""
    await admin_service.delete_tag(db, tag_id, current_user=current_user)
    return success(None)


# ---------------------------------------------------------------------------
# 题目 CRUD（admin.md §6）
# ---------------------------------------------------------------------------


@router.get("/questions")
async def list_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    part: int | None = Query(default=None, ge=1, le=3),
    topic_id: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(draft|published|disabled)$"),
    keyword: str | None = Query(default=None, max_length=100),
    tag_id: str | None = Query(default=None),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """题目列表（admin.md §6.1，含全部状态 draft/published/disabled）。"""
    data = await admin_service.list_questions(
        db,
        page=page,
        page_size=page_size,
        part=part,
        topic_id=topic_id,
        status=status,
        keyword=keyword,
        tag_id=tag_id,
        difficulty=difficulty,
    )
    return success(data)


@router.post("/questions")
async def create_question(
    req: QuestionUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """创建题目（admin.md §6.2，created_by 自动填当前管理员）。"""
    data = await admin_service.create_question(db, req, current_user=current_user)
    return success(data)


@router.get("/questions/{question_id}")
async def get_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """题目详情（admin.md §6.3，管理员可见 draft/disabled，不返回 4002）。"""
    data = await admin_service.get_question_detail(db, question_id)
    return success(data)


@router.put("/questions/{question_id}")
async def update_question(
    question_id: int,
    req: QuestionUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """更新题目（admin.md §6.4，全量替换 + tag_ids 重建，不可物理删除 ADR-010）。"""
    data = await admin_service.update_question(
        db, question_id, req, current_user=current_user
    )
    return success(data)


@router.put("/questions/{question_id}/status")
async def update_question_status(
    question_id: int,
    req: UpdateQuestionStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """切换题目状态（admin.md §6.5，MVP 不限制转换方向）。"""
    data = await admin_service.update_question_status(
        db, question_id, req.status, current_user=current_user
    )
    return success(data)
