"""auth 模块 logout service 单元测试 (auth.md §4)。

MVP 无状态退出（ADR-027）：仅写 user_logout 日志，不撤销 token。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.activity import UserActivityLog
from app.modules.auth import service


@pytest.mark.asyncio
async def test_logout_writes_activity_log() -> None:
    """logout 写入 user_logout 日志，entity_id = user_id。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    await service.logout(db, user_id=1001, ip_address="127.0.0.1")

    assert db.add.call_count == 1
    log: UserActivityLog = db.add.call_args.args[0]
    assert log.user_id == 1001
    assert log.action == "user_logout"
    assert log.entity_type == "user"
    assert log.entity_id == 1001
    assert log.ip_address == "127.0.0.1"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_ip_optional() -> None:
    """ip_address 可选（None 时正常）。"""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    await service.logout(db, user_id=42, ip_address=None)

    log = db.add.call_args.args[0]
    assert log.ip_address is None
