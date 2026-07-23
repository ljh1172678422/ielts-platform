"""Admin Dashboard 测试（Phase 5.1）。

覆盖：
1. service.get_dashboard：组装各 repository 结果为 DashboardData DTO
2. router 鉴权：无 token → 2001，非 admin → 2003，admin → 200 成功
   （用 dependency_overrides 替换 get_current_user/require_admin，避免 DB）
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, require_admin
from app.main import app
from app.models.user import Role, User
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import DashboardData


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_user(*, role: str = "user", status: str = "active") -> User:
    """构造 User 实体（不落 DB，仅用于依赖注入替换）。"""
    r = Role(id=1 if role == "user" else 2, name=role)
    u = User(id=1, email="t@e.com", password_hash="x", role_id=r.id, status=status)
    u.role = r
    return u


# ---------------------------------------------------------------------------
# service 层：组装逻辑
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dashboard_assembles_all_stats() -> None:
    """service 正确组装 repository 返回的各统计为 DashboardData。"""
    with (
        patch("app.modules.admin.service.repo.count_users_total", new=AsyncMock(return_value=1256)),
        patch("app.modules.admin.service.repo.count_users_active_today", new=AsyncMock(return_value=84)),
        patch("app.modules.admin.service.repo.count_users_new_this_week", new=AsyncMock(return_value=32)),
        patch(
            "app.modules.admin.service.repo.count_questions_by_status",
            new=AsyncMock(return_value={"published": 450, "draft": 20, "disabled": 10, "total": 480}),
        ),
        patch(
            "app.modules.admin.service.repo.count_practice_stats",
            new=AsyncMock(return_value={
                "total_sessions": 8920, "total_attempts": 42100,
                "total_recordings": 39800, "total_duration_seconds": 3120000,
            }),
        ),
        patch("app.modules.admin.service.repo.count_topics_total", new=AsyncMock(return_value=24)),
        patch("app.modules.admin.service.repo.count_tags_total", new=AsyncMock(return_value=68)),
    ):
        result = await admin_service.get_dashboard(AsyncMock())

    assert isinstance(result, DashboardData)
    assert result.users.total == 1256
    assert result.users.active_today == 84
    assert result.users.new_this_week == 32
    assert result.questions.total == 480
    assert result.questions.published == 450
    assert result.questions.draft == 20
    assert result.questions.disabled == 10
    assert result.practice.total_sessions == 8920
    assert result.practice.total_attempts == 42100
    assert result.practice.total_recordings == 39800
    assert result.practice.total_duration_seconds == 3120000
    assert result.topics.total == 24
    assert result.tags.total == 68


# ---------------------------------------------------------------------------
# router 层：鉴权（用 dependency_overrides 避免真实 DB）
# ---------------------------------------------------------------------------


def test_dashboard_without_token_returns_401(client: TestClient) -> None:
    """无 Authorization header → 2001/401（admin.md §2.3）。"""
    resp = client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 2001
    assert body["data"] is None


def test_dashboard_with_non_admin_user_returns_403(client: TestClient) -> None:
    """普通用户 → 2003/403（admin.md §1.1）。
    用 dependency_overrides 让 get_current_user 返回 user 角色用户，
    require_admin 走真实逻辑抛 2003。
    """
    normal_user = _make_user(role="user")
    app.dependency_overrides[get_current_user] = lambda: normal_user
    try:
        resp = client.get("/api/v1/admin/dashboard")
        assert resp.status_code == 403
        assert resp.json()["code"] == 2003
    finally:
        app.dependency_overrides.clear()


def test_dashboard_with_admin_returns_stats(client: TestClient) -> None:
    """admin → 200 返回完整统计结构（admin.md §2.2）。"""
    admin_user = _make_user(role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user

    fake = DashboardData(
        users={"total": 10, "active_today": 3, "new_this_week": 2},
        questions={"total": 50, "published": 40, "draft": 8, "disabled": 2},
        practice={
            "total_sessions": 100, "total_attempts": 500,
            "total_recordings": 450, "total_duration_seconds": 36000,
        },
        topics={"total": 5},
        tags={"total": 12},
    )
    with patch("app.modules.admin.router.admin_service.get_dashboard", new=AsyncMock(return_value=fake)):
        try:
            resp = client.get("/api/v1/admin/dashboard")
            assert resp.status_code == 200
            body = resp.json()
            assert body["code"] == 0
            assert body["message"] == "ok"
            data = body["data"]
            assert data["users"]["total"] == 10
            assert data["questions"]["published"] == 40
            assert data["practice"]["total_sessions"] == 100
            assert data["topics"]["total"] == 5
            assert data["tags"]["total"] == 12
        finally:
            app.dependency_overrides.clear()
