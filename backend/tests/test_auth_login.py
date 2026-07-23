"""auth 模块 login service 单元测试 (auth.md §3)。

测可独立验证的逻辑：
- 用户不存在 → 3002/401（防枚举）
- 密码错误 → 3002/401（防枚举，与用户不存在相同 code/message）
- 账号禁用 → 2004/403
- 正常登录 → 更新 last_login_at + 写日志 + 返回 token + id 为 str
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.models.user import Role, User, UserProfile
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest


def _make_user(
    *,
    status: str = "active",
    password: str = "Pass1234!",
) -> User:
    """构造带 role/profile 关系的 User 实体。"""
    role = Role(id=2, name="user")
    user = User(
        id=1001,
        email="alice@example.com",
        password_hash=hash_password(password),
        role_id=2,
        status=status,
        created_at=datetime.now(UTC),
    )
    user.role = role
    user.profile = UserProfile(
        id=1,
        user_id=1001,
        nickname="Alice",
        timezone="Asia/Shanghai",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    return user


def _mock_session(user: User | None) -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=user)
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_login_user_not_found_returns_3002() -> None:
    """用户不存在 → 3002/401（防枚举）。"""
    db = _mock_session(user=None)
    req = LoginRequest(email="nobody@example.com", password="Pass1234!")
    with pytest.raises(AppError) as exc_info:
        await service.login(db, req)
    assert exc_info.value.code == 3002
    assert exc_info.value.http_status == 401
    assert exc_info.value.message == "邮箱或密码错误"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_3002_same_as_not_found() -> None:
    """密码错误 → 3002/401，与用户不存在 code/message 完全一致（防枚举）。"""
    user = _make_user(password="Pass1234!")
    db = _mock_session(user=user)
    req = LoginRequest(email="alice@example.com", password="WrongPass!")
    with pytest.raises(AppError) as exc_info:
        await service.login(db, req)
    assert exc_info.value.code == 3002
    assert exc_info.value.http_status == 401
    assert exc_info.value.message == "邮箱或密码错误"
    # 防枚举关键：与用户不存在的错误信息完全相同
    not_found_msg = "邮箱或密码错误"
    assert exc_info.value.message == not_found_msg


@pytest.mark.asyncio
async def test_login_disabled_returns_2004() -> None:
    """账号禁用 → 2004/403（密码正确后才检查）。"""
    user = _make_user(status="disabled", password="Pass1234!")
    db = _mock_session(user=user)
    req = LoginRequest(email="alice@example.com", password="Pass1234!")
    with pytest.raises(AppError) as exc_info:
        await service.login(db, req)
    assert exc_info.value.code == 2004
    assert exc_info.value.http_status == 403


@pytest.mark.asyncio
async def test_login_success_updates_last_login_and_logs() -> None:
    """正常登录 → 更新 last_login_at + 写 user_login 日志 + 返回 token。"""
    user = _make_user(password="Pass1234!")
    assert user.last_login_at is None
    db = _mock_session(user=user)
    req = LoginRequest(email="alice@example.com", password="Pass1234!")
    data = await service.login(db, req)

    # 响应结构
    assert set(data) == {"user", "access_token", "token_type", "expires_in"}
    assert data["user"]["id"] == "1001"  # ADR-025 str
    assert data["user"]["email"] == "alice@example.com"
    assert data["access_token"].count(".") == 2
    assert data["expires_in"] == 86400
    # last_login_at 已更新
    assert user.last_login_at is not None
    # 写入 1 条日志
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert log_obj.action == "user_login"
    assert log_obj.user_id == 1001
