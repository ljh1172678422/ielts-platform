"""auth 模块 register service 单元测试。

沙箱无 PostgreSQL，用 unittest.mock 模拟 AsyncSession，测可独立验证的逻辑：
- timezone 非法 → 1001/422
- 邮箱已注册 → 3001/409
- role 未种子 → 9000/500
- 正常路径 → 返回含 access_token/user 的 dict，user.id 为 str（ADR-025）
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppError
from app.models.user import Role, User
from app.modules.auth import service
from app.modules.auth.schemas import RegisterRequest


def _mock_session(*, existing_user=None, role=None) -> MagicMock:
    """构造 mock AsyncSession，existing_user 控制邮箱冲突查询返回。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    # 模拟两次 execute：第一次邮箱冲突查询，第二次 role 查询
    results = []

    # 邮箱查询结果
    email_result = MagicMock()
    email_result.scalar_one_or_none = MagicMock(return_value=existing_user)
    results.append(email_result)

    # role 查询结果
    role_result = MagicMock()
    role_result.scalar_one_or_none = MagicMock(return_value=role)
    results.append(role_result)

    db.execute = AsyncMock(side_effect=results)
    return db


@pytest.mark.asyncio
async def test_register_invalid_timezone() -> None:
    """timezone 非法 IANA 名 → AppError 1001/422。"""
    db = _mock_session()
    req = RegisterRequest(
        email="a@b.c", password="pass1234", timezone="Invalid/Foo"
    )
    with pytest.raises(AppError) as exc_info:
        await service.register(db, req)
    assert exc_info.value.code == 1001
    assert exc_info.value.http_status == 422


@pytest.mark.asyncio
async def test_register_email_conflict() -> None:
    """邮箱已注册 → AppError 3001/409。"""
    existing = User(id=1, email="a@b.c", password_hash="x", role_id=1)
    db = _mock_session(existing_user=existing)
    req = RegisterRequest(
        email="a@b.c", password="pass1234", timezone="Asia/Shanghai"
    )
    with pytest.raises(AppError) as exc_info:
        await service.register(db, req)
    assert exc_info.value.code == 3001
    assert exc_info.value.http_status == 409


@pytest.mark.asyncio
async def test_register_role_not_seeded() -> None:
    """user 角色未种子 → AppError 9000/500。"""
    db = _mock_session(existing_user=None, role=None)
    req = RegisterRequest(
        email="a@b.c", password="pass1234", timezone="Asia/Shanghai"
    )
    with pytest.raises(AppError) as exc_info:
        await service.register(db, req)
    assert exc_info.value.code == 9000
    assert exc_info.value.http_status == 500


@pytest.mark.asyncio
async def test_register_success_returns_str_id_and_token() -> None:
    """正常注册 → 返回 dict，user.id 为 str（ADR-025），含 access_token。"""
    role = Role(id=2, name="user")
    db = _mock_session(existing_user=None, role=role)

    # 让构造的 user 在 flush 后获得 id（模拟 DB 自增赋值）
    def _flush_side_effect():
        # user 已被 db.add，找出来赋 id
        for call_args in db.add.call_args_list:
            obj = call_args.args[0]
            if isinstance(obj, User) and obj.id is None:
                obj.id = 1001
                # created_at 由 server_default 提供，flush 后 DB 会回填；
                # 这里手动设避免 None 导致 UserPublic 校验失败
                from datetime import UTC, datetime
                obj.created_at = datetime.now(UTC)

    db.flush.side_effect = _flush_side_effect

    req = RegisterRequest(
        email="alice@example.com",
        password="Alice@2026",
        nickname="Alice",
        timezone="Asia/Shanghai",
    )
    data = await service.register(db, req)

    assert set(data) == {"user", "access_token", "token_type", "expires_in"}
    assert data["access_token"].count(".") == 2  # JWT 三段
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 86400
    # ADR-025: id 序列化为字符串
    assert data["user"]["id"] == "1001"
    assert isinstance(data["user"]["id"], str)
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["role"] == "user"
    assert data["user"]["status"] == "active"
    assert data["user"]["profile"]["nickname"] == "Alice"
    assert data["user"]["profile"]["timezone"] == "Asia/Shanghai"
    assert data["user"]["profile"]["avatar_url"] is None
    # 写入了 user + profile + activity_log 共 3 个对象
    assert db.add.call_count == 3
