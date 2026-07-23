"""users 模块 service 单元测试 (users.md §2/§3/§4)。

测可独立验证的逻辑：
- get_me: 返回 UserPublic，id 为 str
- update_profile: 全量替换 nickname/avatar_url/timezone
- update_password: 旧密码错误 → 3003/400；正确 → 更新 hash
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.models.user import Role, User, UserProfile
from app.modules.users import service
from app.modules.users.schemas import ProfileUpdateRequest


def _make_user(*, password: str = "Pass1234!") -> User:
    role = Role(id=2, name="user")
    user = User(
        id=1001,
        email="alice@example.com",
        password_hash=hash_password(password),
        role_id=2,
        status="active",
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


def _mock_session_first(user: User | None, second_result=None) -> MagicMock:
    """模拟 execute 多次调用：第一次返回 user，第二次（可选）返回 second_result。"""
    db = MagicMock()
    db.flush = AsyncMock()
    results = []
    r1 = MagicMock()
    r1.scalar_one_or_none = MagicMock(return_value=user)
    results.append(r1)
    if second_result is not None:
        results.append(second_result)
    db.execute = AsyncMock(side_effect=results)
    return db


@pytest.mark.asyncio
async def test_get_me_returns_str_id() -> None:
    """get_me 返回 UserPublic，id 为 str（ADR-025）。"""
    user = _make_user()
    db = _mock_session_first(user)
    result = await service.get_me(db, user_id=1001)
    assert result.id == "1001"
    assert isinstance(result.id, str)
    assert result.email == "alice@example.com"
    assert result.role == "user"
    assert result.status == "active"
    assert result.profile.nickname == "Alice"
    assert result.profile.timezone == "Asia/Shanghai"
    assert result.profile.avatar_url is None


@pytest.mark.asyncio
async def test_update_profile_replaces_fields() -> None:
    """update_profile 全量替换 profile 字段。"""
    user = _make_user()
    profile = user.profile
    # update_profile 第一次查 profile，第二次查 user（带 role+profile 关系）
    profile_result = MagicMock()
    profile_result.scalar_one_or_none = MagicMock(return_value=profile)
    user_result = MagicMock()
    user_result.scalar_one = MagicMock(return_value=user)
    db = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(side_effect=[profile_result, user_result])

    req = ProfileUpdateRequest(
        nickname="Alice L.",
        avatar_url="https://cdn.example.com/a.png",
        timezone="America/New_York",
    )
    result = await service.update_profile(db, user_id=1001, req=req)
    # profile 字段已被更新
    assert profile.nickname == "Alice L."
    assert profile.avatar_url == "https://cdn.example.com/a.png"
    assert profile.timezone == "America/New_York"
    # 返回的 UserPublic 反映新值
    assert result.profile.nickname == "Alice L."
    assert result.profile.timezone == "America/New_York"


@pytest.mark.asyncio
async def test_update_profile_clears_nullable_fields() -> None:
    """nickname/avatar_url 传 null → 置 null（全量替换语义）。"""
    user = _make_user()
    profile = user.profile
    profile_result = MagicMock()
    profile_result.scalar_one_or_none = MagicMock(return_value=profile)
    user_result = MagicMock()
    user_result.scalar_one = MagicMock(return_value=user)
    db = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(side_effect=[profile_result, user_result])

    req = ProfileUpdateRequest(nickname=None, avatar_url=None, timezone="Asia/Shanghai")
    await service.update_profile(db, user_id=1001, req=req)
    assert profile.nickname is None
    assert profile.avatar_url is None


@pytest.mark.asyncio
async def test_update_password_wrong_old_returns_3003() -> None:
    """旧密码错误 → 3003/400。"""
    user = _make_user(password="Pass1234!")
    db = _mock_session_first(user)
    with pytest.raises(AppError) as exc_info:
        await service.update_password(db, user_id=1001, old_password="Wrong!", new_password="New12345!")
    assert exc_info.value.code == 3003
    assert exc_info.value.http_status == 400


@pytest.mark.asyncio
async def test_update_password_success_updates_hash() -> None:
    """旧密码正确 → password_hash 更新为新密码的哈希。"""
    user = _make_user(password="Pass1234!")
    old_hash = user.password_hash
    db = _mock_session_first(user)
    await service.update_password(db, user_id=1001, old_password="Pass1234!", new_password="NewPass123!")
    # hash 已变化
    assert user.password_hash != old_hash
    # 新 hash 能验证新密码
    assert verify_password("NewPass123!", user.password_hash)
    # 旧密码不再匹配
    assert not verify_password("Pass1234!", user.password_hash)
