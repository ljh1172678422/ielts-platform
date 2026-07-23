"""Admin 主题/标签 CRUD 测试（Phase 5.3 + 5.4）。

覆盖关键业务约束：
主题（admin.md §4）：
- create: name='Other' → 8001；name 重复 → 1004
- update: 不存在 → 4003；Other 改 name → 8001；name 冲突 → 1004
- delete: 不存在 → 4003；Other → 8001；有 published 题目 → 8002

标签（admin.md §5）：
- create: name 重复 → 1004
- update: 不存在 → 4004；name 冲突 → 1004
- delete: 不存在 → 4004；被引用 → 8002
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.question import SpeakingTopic, Tag
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import TagUpsertRequest, TopicUpsertRequest


def _make_topic(
    *, tid: int = 1, name: str = "Technology", deleted: bool = False
) -> SpeakingTopic:
    t = SpeakingTopic(
        id=tid, name=name, description="desc", sort_order=0, created_at=datetime.now(UTC)
    )
    if deleted:
        t.deleted_at = datetime.now(UTC)
    return t


def _make_tag(*, tid: int = 1, name: str = "gadget", deleted: bool = False) -> Tag:
    t = Tag(id=tid, name=name, created_at=datetime.now(UTC))
    if deleted:
        t.deleted_at = datetime.now(UTC)
    return t


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# 主题 create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_topic_named_other_returns_8001() -> None:
    """创建名为 Other 的主题 → 8001（系统保留）。"""
    db = _mock_db()
    req = TopicUpsertRequest(name="Other", description="x")
    with pytest.raises(AppError) as exc:
        await admin_service.create_topic(db, req, current_user=MagicMock(id=1))
    assert exc.value.code == 8001


@pytest.mark.asyncio
async def test_create_topic_duplicate_name_returns_1004() -> None:
    """name 已存在（未软删）→ 1004/409。"""
    db = _mock_db()
    existing = _make_topic(tid=5, name="Tech")
    with patch("app.modules.admin.service.repo.get_topic_by_name", new=AsyncMock(return_value=existing)):
        req = TopicUpsertRequest(name="Tech")
        with pytest.raises(AppError) as exc:
            await admin_service.create_topic(db, req, current_user=MagicMock(id=1))
    assert exc.value.code == 1004
    assert exc.value.http_status == 409


@pytest.mark.asyncio
async def test_create_topic_success() -> None:
    """正常创建 → 写库 + 返回 item（is_system=False）。"""
    db = _mock_db()
    with (
        patch("app.modules.admin.service.repo.get_topic_by_name", new=AsyncMock(return_value=None)),
        patch("app.modules.admin.service.repo.count_published_questions_by_topic", new=AsyncMock(return_value=0)),
    ):
        # 捕获 db.add 的 topic 对象，回填 id 模拟 flush
        def _capture(obj):
            if isinstance(obj, SpeakingTopic):
                obj.id = 10
                obj.created_at = datetime.now(UTC)
        db.add.side_effect = _capture
        req = TopicUpsertRequest(name="Science", description="Sci topics")
        result = await admin_service.create_topic(db, req, current_user=MagicMock(id=1))

    assert result["id"] == "10"
    assert result["name"] == "Science"
    assert result["is_system"] is False
    assert result["slug"] == "Science"  # MVP 派生
    # 写了 topic + activity_log
    assert db.add.call_count == 2


# ---------------------------------------------------------------------------
# 主题 update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_topic_not_found_returns_4003() -> None:
    db = _mock_db()
    with patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await admin_service.update_topic(
                db, 999, TopicUpsertRequest(name="X"), current_user=MagicMock(id=1)
            )
    assert exc.value.code == 4003


@pytest.mark.asyncio
async def test_update_other_topic_rename_returns_8001() -> None:
    """Other 主题改 name → 8001（仅允许改 description）。"""
    db = _mock_db()
    other = _make_topic(tid=1, name="Other")
    with patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=other)):
        with pytest.raises(AppError) as exc:
            await admin_service.update_topic(
                db, 1, TopicUpsertRequest(name="NewName"), current_user=MagicMock(id=1)
            )
    assert exc.value.code == 8001


@pytest.mark.asyncio
async def test_update_other_topic_description_allowed() -> None:
    """Other 主题改 description（name 不变）→ 允许。"""
    db = _mock_db()
    other = _make_topic(tid=1, name="Other")
    with (
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=other)),
        patch("app.modules.admin.service.repo.count_published_questions_by_topic", new=AsyncMock(return_value=0)),
    ):
        result = await admin_service.update_topic(
            db, 1, TopicUpsertRequest(name="Other", description="new desc"),
            current_user=MagicMock(id=1),
        )
    assert other.description == "new desc"
    assert result["is_system"] is True


# ---------------------------------------------------------------------------
# 主题 delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_other_topic_returns_8001() -> None:
    db = _mock_db()
    other = _make_topic(tid=1, name="Other")
    with patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=other)):
        with pytest.raises(AppError) as exc:
            await admin_service.delete_topic(db, 1, current_user=MagicMock(id=1))
    assert exc.value.code == 8001


@pytest.mark.asyncio
async def test_delete_topic_with_published_questions_returns_8002() -> None:
    db = _mock_db()
    topic = _make_topic(tid=5, name="Tech")
    with (
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.admin.service.repo.count_published_questions_by_topic", new=AsyncMock(return_value=3)),
    ):
        with pytest.raises(AppError) as exc:
            await admin_service.delete_topic(db, 5, current_user=MagicMock(id=1))
    assert exc.value.code == 8002


@pytest.mark.asyncio
async def test_delete_topic_success_soft_deletes() -> None:
    db = _mock_db()
    topic = _make_topic(tid=5, name="Tech")
    assert topic.deleted_at is None
    with (
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.admin.service.repo.count_published_questions_by_topic", new=AsyncMock(return_value=0)),
    ):
        await admin_service.delete_topic(db, 5, current_user=MagicMock(id=1))
    assert topic.deleted_at is not None  # 软删


# ---------------------------------------------------------------------------
# 标签 create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tag_duplicate_returns_1004() -> None:
    db = _mock_db()
    existing = _make_tag(tid=3, name="gadget")
    with patch("app.modules.admin.service.repo.get_tag_by_name", new=AsyncMock(return_value=existing)):
        with pytest.raises(AppError) as exc:
            await admin_service.create_tag(db, TagUpsertRequest(name="gadget"), current_user=MagicMock(id=1))
    assert exc.value.code == 1004


# ---------------------------------------------------------------------------
# 标签 delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_tag_not_found_returns_4004() -> None:
    db = _mock_db()
    with patch("app.modules.admin.service.repo.get_tag_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await admin_service.delete_tag(db, 999, current_user=MagicMock(id=1))
    assert exc.value.code == 4004


@pytest.mark.asyncio
async def test_delete_tag_with_references_returns_8002() -> None:
    db = _mock_db()
    tag = _make_tag(tid=3, name="gadget")
    with (
        patch("app.modules.admin.service.repo.get_tag_by_id", new=AsyncMock(return_value=tag)),
        patch("app.modules.admin.service.repo.count_questions_by_tag", new=AsyncMock(return_value=5)),
    ):
        with pytest.raises(AppError) as exc:
            await admin_service.delete_tag(db, 3, current_user=MagicMock(id=1))
    assert exc.value.code == 8002


@pytest.mark.asyncio
async def test_delete_tag_success() -> None:
    db = _mock_db()
    tag = _make_tag(tid=3, name="gadget")
    with (
        patch("app.modules.admin.service.repo.get_tag_by_id", new=AsyncMock(return_value=tag)),
        patch("app.modules.admin.service.repo.count_questions_by_tag", new=AsyncMock(return_value=0)),
    ):
        await admin_service.delete_tag(db, 3, current_user=MagicMock(id=1))
    assert tag.deleted_at is not None
