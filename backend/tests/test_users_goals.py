"""users 模块 goals service 单元测试 (users.md §5/§6/§7, ADR-014)。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppError
from app.models.user import UserGoal
from app.modules.users import service
from app.modules.users.schemas import UserGoalCreate, UserGoalUpdate


def _make_goal(
    *,
    id: int = 51,
    status: str = "active",
    target_score: float | None = 7.0,
) -> UserGoal:
    now = datetime.now(UTC)
    return UserGoal(
        id=id,
        user_id=1001,
        target_score=target_score,
        current_level="6.0",
        exam_date=None,
        daily_goal_minutes=60,
        weekly_goal_minutes=360,
        status=status,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_goals_splits_current_and_history() -> None:
    """list_goals 拆分 current(active) 与 history(其余)，按 updated_at DESC。"""
    active = _make_goal(id=51, status="active")
    achieved = _make_goal(id=50, status="achieved")
    archived = _make_goal(id=49, status="archived")
    # repository 按 created_at DESC 返回
    goals = [active, achieved, archived]

    db = MagicMock()
    # patch repository.get_goals_by_user
    import app.modules.users.service as svc

    orig = svc.get_goals_by_user
    svc.get_goals_by_user = AsyncMock(return_value=goals)
    try:
        result = await service.list_goals(db, user_id=1001)
    finally:
        svc.get_goals_by_user = orig

    assert result.current is not None
    assert result.current.id == "51"
    assert result.current.status == "active"
    assert len(result.history) == 2


@pytest.mark.asyncio
async def test_create_goal_all_fields_empty_returns_1001() -> None:
    """全字段为空 → 1001/422。"""
    db = MagicMock()
    req = UserGoalCreate()  # 全 None
    with pytest.raises(AppError) as exc_info:
        await service.create_goal(db, user_id=1001, req=req)
    assert exc_info.value.code == 1001
    assert exc_info.value.http_status == 422


@pytest.mark.asyncio
async def test_create_goal_active_exists_returns_1004() -> None:
    """已存在 active 目标 → 1004/409（ADR-014）。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    import app.modules.users.service as svc

    orig = svc.get_active_goal
    svc.get_active_goal = AsyncMock(return_value=_make_goal())
    try:
        req = UserGoalCreate(target_score=7.0)
        with pytest.raises(AppError) as exc_info:
            await service.create_goal(db, user_id=1001, req=req)
        assert exc_info.value.code == 1004
        assert exc_info.value.http_status == 409
    finally:
        svc.get_active_goal = orig


@pytest.mark.asyncio
async def test_create_goal_success_returns_str_id() -> None:
    """正常创建 → 返回 Goal，id 为 str，status=active，写日志。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    def _flush_side_effect():
        for call_args in db.add.call_args_list:
            obj = call_args.args[0]
            if isinstance(obj, UserGoal) and obj.id is None:
                obj.id = 52
                now = datetime.now(UTC)
                obj.created_at = now
                obj.updated_at = now

    db.flush.side_effect = _flush_side_effect

    import app.modules.users.service as svc

    orig = svc.get_active_goal
    svc.get_active_goal = AsyncMock(return_value=None)
    try:
        req = UserGoalCreate(target_score=7.5, daily_goal_minutes=30)
        result = await service.create_goal(db, user_id=1001, req=req)
    finally:
        svc.get_active_goal = orig

    assert result.id == "52"
    assert isinstance(result.id, str)
    assert result.status == "active"
    assert result.target_score == 7.5
    # 写入了 goal + activity_log
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_update_goal_not_found_returns_1002() -> None:
    """goal 不存在/不属于用户 → 1002/404。"""
    db = MagicMock()
    import app.modules.users.service as svc

    orig = svc.get_goal_by_id
    svc.get_goal_by_id = AsyncMock(return_value=None)
    try:
        req = UserGoalUpdate(status="archived")
        with pytest.raises(AppError) as exc_info:
            await service.update_goal(db, user_id=1001, goal_id=999, req=req)
        assert exc_info.value.code == 1002
        assert exc_info.value.http_status == 404
    finally:
        svc.get_goal_by_id = orig


@pytest.mark.asyncio
async def test_update_goal_to_active_with_existing_active_returns_1004() -> None:
    """archived→active 但已有其他 active → 1004/409。"""
    archived_goal = _make_goal(id=50, status="archived")
    other_active = _make_goal(id=51, status="active")
    db = MagicMock()
    db.flush = AsyncMock()
    import app.modules.users.service as svc

    orig_goal = svc.get_goal_by_id
    orig_active = svc.get_active_goal
    svc.get_goal_by_id = AsyncMock(return_value=archived_goal)
    svc.get_active_goal = AsyncMock(return_value=other_active)
    try:
        req = UserGoalUpdate(status="active", target_score=7.0)
        with pytest.raises(AppError) as exc_info:
            await service.update_goal(db, user_id=1001, goal_id=50, req=req)
        assert exc_info.value.code == 1004
    finally:
        svc.get_goal_by_id = orig_goal
        svc.get_active_goal = orig_active


@pytest.mark.asyncio
async def test_update_goal_status_change_writes_log() -> None:
    """status 变化 → 写 goal_updated 日志。"""
    goal = _make_goal(id=50, status="active")
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    import app.modules.users.service as svc

    orig = svc.get_goal_by_id
    svc.get_goal_by_id = AsyncMock(return_value=goal)
    try:
        req = UserGoalUpdate(status="achieved", target_score=7.0)
        result = await service.update_goal(db, user_id=1001, goal_id=50, req=req)
    finally:
        svc.get_goal_by_id = orig

    assert result.status == "achieved"
    assert goal.status == "achieved"
    # 写了 1 条日志（status 变化）
    assert db.add.call_count == 1
    log = db.add.call_args.args[0]
    assert log.action == "goal_updated"
