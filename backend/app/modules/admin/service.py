"""Admin 模块业务逻辑（system-architecture §3：service 层）。

Phase 5.1 Dashboard：聚合各表统计返回概览。
后续 5.2-5.5 在本文件追加用户/主题/标签/题目 service。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.activity import UserActivityLog
from app.models.user import User
from app.modules.admin import repository as repo
from app.modules.admin.schemas import (
    AdminUserListItem,
    DashboardData,
    DashboardPractice,
    DashboardQuestions,
    DashboardTags,
    DashboardTopics,
    DashboardUsers,
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
