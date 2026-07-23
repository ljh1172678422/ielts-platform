"""Admin 模块业务逻辑（system-architecture §3：service 层）。

Phase 5.1 Dashboard：聚合各表统计返回概览。
后续 5.2-5.5 在本文件追加用户/主题/标签/题目 service。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin import repository as repo
from app.modules.admin.schemas import (
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
