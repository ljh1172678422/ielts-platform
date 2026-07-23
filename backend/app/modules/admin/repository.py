"""Admin 模块 SQLAlchemy 查询封装（system-architecture §3）。

Phase 5.1 Dashboard：聚合统计查询。
后续 5.2-5.5 在本文件追加用户/主题/标签/题目 CRUD 查询。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.question import (
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
