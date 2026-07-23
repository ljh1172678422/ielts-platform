"""Admin 题目 CRUD 测试（Phase 5.5）。

覆盖关键业务约束（admin.md §6）：
- create: topic_id 不存在 → 4003；tag_ids 不存在 → 4004；成功 → created_by 自动填 + 默认 draft
- get: 不存在 → 4001；成功 → 含 content/cue_card
- update: 不存在 → 4001；topic 不存在 → 4003；成功 → 字段替换 + tag 重建
- status: 不存在 → 4001；成功 → 状态切换 + 写日志

practice_count 在 Phase 5 占位 0（practice_session_questions 表属 Phase 7）。
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.question import SpeakingQuestion, SpeakingTopic, Tag
from app.modules.admin import service as admin_service
from app.modules.admin.schemas import QuestionUpsertRequest


def _make_topic(*, tid: int = 5, name: str = "Technology") -> SpeakingTopic:
    return SpeakingTopic(
        id=tid,
        name=name,
        description="desc",
        sort_order=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_tag(*, tid: int = 12, name: str = "gadget") -> Tag:
    return Tag(id=tid, name=name, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))


def _make_question(
    *,
    qid: int = 101,
    status: str = "draft",
    topic: SpeakingTopic | None = None,
    tags: list[Tag] | None = None,
    created_by: int | None = 1,
) -> SpeakingQuestion:
    """构造带 topic/tags 关系的 SpeakingQuestion（关系手动 attach）。"""
    q = SpeakingQuestion(
        id=qid,
        part=2,
        topic_id=topic.id if topic else 5,
        title="Describe a useful object",
        content="Tell me about an object you use daily.",
        cue_card="You should say: what it is...",
        difficulty=3,
        status=status,
        source_type="custom",
        source_name="自编练习题",
        created_by=created_by,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    q.topic = topic or _make_topic()
    q.tags = tags or []
    return q


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_question_topic_not_found_returns_4003() -> None:
    """topic_id 不存在 → 4003/404。"""
    db = _mock_db()
    req = QuestionUpsertRequest(
        part=2, title="t", content="c", topic_id="999",
        source_type="custom", source_name="src",
    )
    with patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await admin_service.create_question(db, req, current_user=MagicMock(id=1))
    assert exc.value.code == 4003
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_create_question_tag_not_found_returns_4004() -> None:
    """tag_ids 中某 id 不存在 → 4004/404。"""
    db = _mock_db()
    topic = _make_topic()
    req = QuestionUpsertRequest(
        part=2, title="t", content="c", topic_id="5",
        tag_ids=["12", "999"], source_type="custom", source_name="src",
    )
    with (
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.admin.service.repo.get_existing_tags", new=AsyncMock(return_value=[_make_tag(tid=12)])),
    ):
        with pytest.raises(AppError) as exc:
            await admin_service.create_question(db, req, current_user=MagicMock(id=1))
    assert exc.value.code == 4004
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_create_question_invalid_topic_id_returns_1001() -> None:
    """topic_id 非数字字符串 → 1001/422。"""
    db = _mock_db()
    req = QuestionUpsertRequest(
        part=2, title="t", content="c", topic_id="abc",
        source_type="custom", source_name="src",
    )
    with pytest.raises(AppError) as exc:
        await admin_service.create_question(db, req, current_user=MagicMock(id=1))
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


@pytest.mark.asyncio
async def test_create_question_success_defaults_draft_and_sets_created_by() -> None:
    """正常创建 → 默认 status=draft + created_by=当前管理员 + 返回详情。"""
    db = _mock_db()
    topic = _make_topic()
    tag = _make_tag(tid=12, name="gadget")
    req = QuestionUpsertRequest(
        part=2, title="Describe X", content="content body", cue_card="cue",
        topic_id="5", tag_ids=["12"], difficulty=3,
        source_type="custom", source_name="自编",
    )
    with (
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.admin.service.repo.get_existing_tags", new=AsyncMock(return_value=[tag])),
    ):
        def _capture(obj):
            if isinstance(obj, SpeakingQuestion):
                obj.id = 101
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)
        db.add.side_effect = _capture
        result = await admin_service.create_question(db, req, current_user=MagicMock(id=7))

    assert result["id"] == "101"
    assert result["status"] == "draft"  # 默认
    assert result["created_by"] == "7"  # 当前管理员
    assert result["topic"] == {"id": "5", "name": "Technology"}
    assert result["tags"] == [{"id": "12", "name": "gadget"}]
    assert result["content"] == "content body"
    assert result["cue_card"] == "cue"
    assert result["practice_count"] == 0  # Phase 5 占位
    # 写了 question + 1 个 question_tag + activity_log
    assert db.add.call_count == 3


@pytest.mark.asyncio
async def test_create_question_with_published_status() -> None:
    """显式传 status=published → 创建即上架。"""
    db = _mock_db()
    topic = _make_topic()
    req = QuestionUpsertRequest(
        part=1, title="t", content="c", topic_id="5",
        source_type="official", source_name="剑桥真题",
        status="published",
    )
    with (
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.admin.service.repo.get_existing_tags", new=AsyncMock(return_value=[])),
    ):
        def _capture(obj):
            if isinstance(obj, SpeakingQuestion):
                obj.id = 102
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)
        db.add.side_effect = _capture
        result = await admin_service.create_question(db, req, current_user=MagicMock(id=1))
    assert result["status"] == "published"


# ---------------------------------------------------------------------------
# get detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_question_not_found_returns_4001() -> None:
    """题目不存在 → 4001/404（admin 不返回 4002）。"""
    db = _mock_db()
    with patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await admin_service.get_question_detail(db, 999)
    assert exc.value.code == 4001
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_get_question_returns_detail_with_content() -> None:
    """管理员可见 draft/disabled，返回完整详情（含 content/cue_card）。"""
    db = _mock_db()
    tag = _make_tag(tid=12, name="gadget")
    question = _make_question(qid=101, status="disabled", tags=[tag])
    with patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=question)):
        result = await admin_service.get_question_detail(db, 101)
    # disabled 题目对 admin 可见（不返回 4002）
    assert result["id"] == "101"
    assert result["status"] == "disabled"
    assert result["content"] == "Tell me about an object you use daily."
    assert result["cue_card"] == "You should say: what it is..."
    assert result["topic"] == {"id": "5", "name": "Technology"}


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_question_not_found_returns_4001() -> None:
    db = _mock_db()
    req = QuestionUpsertRequest(
        part=2, title="t", content="c", topic_id="5",
        source_type="custom", source_name="src",
    )
    with patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await admin_service.update_question(db, 999, req, current_user=MagicMock(id=1))
    assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_update_question_topic_not_found_returns_4003() -> None:
    db = _mock_db()
    question = _make_question()
    req = QuestionUpsertRequest(
        part=2, title="t", content="c", topic_id="999",
        source_type="custom", source_name="src",
    )
    with (
        patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=question)),
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(AppError) as exc:
            await admin_service.update_question(db, 101, req, current_user=MagicMock(id=1))
    assert exc.value.code == 4003


@pytest.mark.asyncio
async def test_update_question_success_replaces_fields_and_tags() -> None:
    """更新 → 全量替换字段 + tag 重建（DELETE 旧 + INSERT 新）。"""
    db = _mock_db()
    old_question = _make_question(qid=101, status="draft", tags=[_make_tag(tid=12, name="gadget")])
    new_topic = _make_topic(tid=6, name="Science")
    new_tag = _make_tag(tid=20, name="education")
    req = QuestionUpsertRequest(
        part=1, title="New Title", content="new content", cue_card="new cue",
        topic_id="6", tag_ids=["20"], difficulty=5,
        source_type="official", source_name="剑桥真题", status="published",
    )
    with (
        patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=old_question)),
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=new_topic)),
        patch("app.modules.admin.service.repo.get_existing_tags", new=AsyncMock(return_value=[new_tag])),
        patch("app.modules.admin.service.repo.replace_question_tags", new=AsyncMock()) as replace_mock,
    ):
        result = await admin_service.update_question(db, 101, req, current_user=MagicMock(id=1))

    # 字段被替换
    assert old_question.part == 1
    assert old_question.title == "New Title"
    assert old_question.content == "new content"
    assert old_question.topic_id == 6
    assert old_question.status == "published"
    assert old_question.source_type == "official"
    # tag 重建被调用（传入新 tag id 列表）
    replace_mock.assert_awaited_once_with(db, 101, [20])
    # 返回详情反映新关系
    assert result["topic"] == {"id": "6", "name": "Science"}
    assert result["tags"] == [{"id": "20", "name": "education"}]
    assert result["status"] == "published"


@pytest.mark.asyncio
async def test_update_question_status_none_keeps_original() -> None:
    """update 时 status 不传（None）→ 保持原 status 不变。"""
    db = _mock_db()
    question = _make_question(qid=101, status="published")
    req = QuestionUpsertRequest(
        part=2, title="t", content="c", topic_id="5",
        source_type="custom", source_name="src",
        # status 不传
    )
    with (
        patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=question)),
        patch("app.modules.admin.service.repo.get_topic_by_id", new=AsyncMock(return_value=_make_topic())),
        patch("app.modules.admin.service.repo.get_existing_tags", new=AsyncMock(return_value=[])),
        patch("app.modules.admin.service.repo.replace_question_tags", new=AsyncMock()),
    ):
        await admin_service.update_question(db, 101, req, current_user=MagicMock(id=1))
    assert question.status == "published"  # 保持原值


# ---------------------------------------------------------------------------
# status 切换
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_question_status_not_found_returns_4001() -> None:
    db = _mock_db()
    with patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await admin_service.update_question_status(
                db, 999, "published", current_user=MagicMock(id=1)
            )
    assert exc.value.code == 4001


@pytest.mark.asyncio
async def test_update_question_status_success_logs_and_changes() -> None:
    """状态切换 → 更新 status + 写 status_changed 日志（含 old/new）。"""
    db = _mock_db()
    question = _make_question(qid=101, status="draft")
    with patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=question)):
        result = await admin_service.update_question_status(
            db, 101, "published", current_user=MagicMock(id=1)
        )
    assert question.status == "published"
    assert result["status"] == "published"
    # 写了 1 条 status_changed 日志
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert log_obj.action == "question_status_changed"
    assert log_obj.metadata_ == {"old": "draft", "new": "published"}


@pytest.mark.asyncio
async def test_update_question_status_disabled_to_published_allowed() -> None:
    """MVP 不限制转换方向：disabled → published 允许。"""
    db = _mock_db()
    question = _make_question(qid=101, status="disabled")
    with patch("app.modules.admin.service.repo.get_question_by_id", new=AsyncMock(return_value=question)):
        await admin_service.update_question_status(
            db, 101, "published", current_user=MagicMock(id=1)
        )
    assert question.status == "published"
