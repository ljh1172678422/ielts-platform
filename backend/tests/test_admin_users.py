"""Admin 用户管理测试（Phase 5.2）。

覆盖 admin.md §3.2 update_user_status 的 4 个业务路径：
1. target 不存在 → 1002/404
2. target == current → 8006/400（防自锁）
3. target.role == admin → 8007/400（防互操作）
4. 正常 → status 更新 + 写 activity_log + 返回摘要
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.activity import UserActivityLog
from app.models.user import Role, User, UserProfile
from app.modules.admin import service as admin_service


def _make_user(
    *,
    uid: int = 1001,
    role: str = "user",
    status: str = "active",
    email: str = "target@example.com",
    nickname: str = "Target",
) -> User:
    r = Role(id=1 if role == "user" else 2, name=role)
    u = User(
        id=uid,
        email=email,
        password_hash="x",
        role_id=r.id,
        status=status,
        created_at=datetime.now(UTC),
    )
    u.role = r
    u.profile = UserProfile(id=uid * 10, user_id=uid, nickname=nickname, timezone="Asia/Shanghai")
    return u


def _mock_db() -> MagicMock:
    """mock AsyncSession：add/flush 记录调用。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# update_user_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_target_not_found_returns_1002() -> None:
    """target 不存在 → 1002/404（admin.md §3.2）。"""
    db = _mock_db()
    current = _make_user(uid=1, role="admin", email="admin@e.com")
    with patch("app.modules.admin.service.repo.get_user_by_id_admin", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc_info:
            await admin_service.update_user_status(
                db, target_id=9999, new_status="disabled", current_user=current
            )
    assert exc_info.value.code == 1002
    assert exc_info.value.http_status == 404
    assert "用户不存在" in exc_info.value.message


@pytest.mark.asyncio
async def test_update_status_self_lock_returns_8006() -> None:
    """target == current → 8006/400（防自锁，admin.md §3.2）。"""
    db = _mock_db()
    current = _make_user(uid=1, role="admin", email="admin@e.com")
    # target 就是 current 自己
    target = current
    with patch("app.modules.admin.service.repo.get_user_by_id_admin", new=AsyncMock(return_value=target)):
        with pytest.raises(AppError) as exc_info:
            await admin_service.update_user_status(
                db, target_id=1, new_status="disabled", current_user=current
            )
    assert exc_info.value.code == 8006
    assert exc_info.value.http_status == 400
    # 未写库
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_update_status_target_admin_returns_8007() -> None:
    """target.role == admin → 8007/400（防管理员互操作，admin.md §3.2）。"""
    db = _mock_db()
    current = _make_user(uid=1, role="admin", email="admin1@e.com")
    target = _make_user(uid=2, role="admin", email="admin2@e.com")  # 另一个管理员
    with patch("app.modules.admin.service.repo.get_user_by_id_admin", new=AsyncMock(return_value=target)):
        with pytest.raises(AppError) as exc_info:
            await admin_service.update_user_status(
                db, target_id=2, new_status="disabled", current_user=current
            )
    assert exc_info.value.code == 8007
    assert exc_info.value.http_status == 400
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_update_status_success_updates_and_logs() -> None:
    """正常禁用 user → status 更新 + 写 activity_log + 返回摘要（admin.md §3.2）。"""
    db = _mock_db()
    current = _make_user(uid=1, role="admin", email="admin@e.com")
    target = _make_user(uid=100, role="user", status="active", email="alice@e.com", nickname="Alice")
    assert target.status == "active"

    with patch("app.modules.admin.service.repo.get_user_by_id_admin", new=AsyncMock(return_value=target)):
        result = await admin_service.update_user_status(
            db, target_id=100, new_status="disabled", current_user=current
        )

    # status 已更新
    assert target.status == "disabled"
    # 写了 1 条 activity_log
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert isinstance(log_obj, UserActivityLog)
    assert log_obj.action == "user_status_changed"
    assert log_obj.user_id == 1  # current
    assert log_obj.entity_id == 100  # target
    assert log_obj.metadata_ == {"old": "active", "new": "disabled"}
    # 返回摘要结构
    assert result["id"] == "100"
    assert result["email"] == "alice@e.com"
    assert result["role"] == "user"
    assert result["status"] == "disabled"
    assert result["nickname"] == "Alice"
