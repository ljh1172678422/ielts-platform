"""Questions 模块（用户端）测试（Phase 6.1-6.3）。

覆盖关键业务约束（questions.md）：
- list: published 可见 + 批量补 is_favorited/practice_count + 分页 total_pages
- detail: 4001(不存在/draft 防探测)/4002(disabled) 分级 + published 完整字段
- favorite: 非published→4001(防探测) + 幂等(重复不写日志) + 实际新增写日志
- unfavorite: 幂等 + 不校验题目状态 + 实际删除写日志
- router: path id 非法→1001，query id 非法→空列表语义(-1)
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.question import SpeakingQuestion, SpeakingTopic, Tag
from app.modules.questions import service as question_service


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
    status: str = "published",
    topic: SpeakingTopic | None = None,
    tags: list[Tag] | None = None,
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
        created_by=1,
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
# list（questions.md §2）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_questions_returns_items_with_favorited_and_practice_count() -> None:
    """列表 → 批量补 is_favorited/practice_count，返回分页结构。"""
    db = _mock_db()
    q1 = _make_question(qid=101)
    q2 = _make_question(qid=102, topic=_make_topic(tid=6, name="Science"))
    with (
        patch("app.modules.questions.service.repo.list_published_questions", new=AsyncMock(return_value=([q1, q2], 2))),
        patch("app.modules.questions.service.repo.batch_favorited_question_ids", new=AsyncMock(return_value={101})),
        patch("app.modules.questions.service.repo.batch_practice_counts", new=AsyncMock(return_value={102: 42})),
    ):
        result = await question_service.list_questions(
            db, current_user=MagicMock(id=1), page=1, page_size=20
        )
    assert result["total"] == 2
    assert result["page"] == 1
    assert result["page_size"] == 20
    assert result["total_pages"] == 1
    assert len(result["items"]) == 2
    # q1 已收藏，practice_count=0（未在 counts 中）
    assert result["items"][0]["is_favorited"] is True
    assert result["items"][0]["practice_count"] == 0
    # q2 未收藏，practice_count=42
    assert result["items"][1]["is_favorited"] is False
    assert result["items"][1]["practice_count"] == 42
    # 列表项不含 content/cue_card/tags（§2.2）
    assert "content" not in result["items"][0]
    assert "tags" not in result["items"][0]


@pytest.mark.asyncio
async def test_list_questions_total_pages_ceiling() -> None:
    """total_pages 向上取整：total=21, page_size=20 → 2 页。"""
    db = _mock_db()
    with (
        patch("app.modules.questions.service.repo.list_published_questions", new=AsyncMock(return_value=([], 21))),
        patch("app.modules.questions.service.repo.batch_favorited_question_ids", new=AsyncMock(return_value=set())),
        patch("app.modules.questions.service.repo.batch_practice_counts", new=AsyncMock(return_value={})),
    ):
        result = await question_service.list_questions(
            db, current_user=MagicMock(id=1), page=2, page_size=20
        )
    assert result["total_pages"] == 2
    assert result["page"] == 2


@pytest.mark.asyncio
async def test_list_questions_passes_filters_and_sort_to_repo() -> None:
    """筛选参数 + sort 正确透传到 repo（含 is_favorited + user_id）。"""
    db = _mock_db()
    list_mock = AsyncMock(return_value=([], 0))
    with (
        patch("app.modules.questions.service.repo.list_published_questions", new=list_mock),
        patch("app.modules.questions.service.repo.batch_favorited_question_ids", new=AsyncMock(return_value=set())),
        patch("app.modules.questions.service.repo.batch_practice_counts", new=AsyncMock(return_value={})),
    ):
        await question_service.list_questions(
            db,
            current_user=MagicMock(id=7),
            page=1,
            page_size=10,
            part=2,
            topic_id=5,
            difficulty=3,
            keyword="describe",
            tag_id=12,
            is_favorited=True,
            sort="popular",
        )
    kwargs = list_mock.call_args.kwargs
    assert kwargs["part"] == 2
    assert kwargs["topic_id"] == 5
    assert kwargs["tag_id"] == 12
    assert kwargs["difficulty"] == 3
    assert kwargs["keyword"] == "describe"
    assert kwargs["is_favorited"] is True
    assert kwargs["sort"] == "popular"
    assert kwargs["user_id"] == 7


# ---------------------------------------------------------------------------
# detail（questions.md §3）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detail_not_found_returns_4001() -> None:
    """题目不存在 → 4001/404。"""
    db = _mock_db()
    with patch("app.modules.questions.service.repo.get_question_with_status", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await question_service.get_question_detail(db, 999, current_user=MagicMock(id=1))
    assert exc.value.code == 4001
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_get_detail_draft_returns_4001_to_prevent_probe() -> None:
    """draft → 4001/404（草稿等同不存在，防探测，§3.4/§6.1）。"""
    db = _mock_db()
    question = _make_question(qid=101, status="draft")
    with patch("app.modules.questions.service.repo.get_question_with_status", new=AsyncMock(return_value=question)):
        with pytest.raises(AppError) as exc:
            await question_service.get_question_detail(db, 101, current_user=MagicMock(id=1))
    assert exc.value.code == 4001
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_get_detail_disabled_returns_4002() -> None:
    """disabled → 4002/400（明确"已下架"，区分 4001，§3.3）。"""
    db = _mock_db()
    question = _make_question(qid=101, status="disabled")
    with patch("app.modules.questions.service.repo.get_question_with_status", new=AsyncMock(return_value=question)):
        with pytest.raises(AppError) as exc:
            await question_service.get_question_detail(db, 101, current_user=MagicMock(id=1))
    assert exc.value.code == 4002
    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_get_detail_published_returns_full_fields_without_sensitive() -> None:
    """published → 完整详情（含 content/cue_card/tags/source_*），不含 created_by/status/updated_at。"""
    db = _mock_db()
    tag = _make_tag(tid=12, name="gadget")
    question = _make_question(qid=101, status="published", tags=[tag])
    with (
        patch("app.modules.questions.service.repo.get_question_with_status", new=AsyncMock(return_value=question)),
        patch("app.modules.questions.service.repo.batch_favorited_question_ids", new=AsyncMock(return_value={101})),
        patch("app.modules.questions.service.repo.batch_practice_counts", new=AsyncMock(return_value={101: 5})),
    ):
        result = await question_service.get_question_detail(db, 101, current_user=MagicMock(id=1))
    assert result["id"] == "101"
    assert result["content"] == "Tell me about an object you use daily."
    assert result["cue_card"] == "You should say: what it is..."
    assert result["topic"] == {"id": "5", "name": "Technology"}
    assert result["tags"] == [{"id": "12", "name": "gadget"}]
    assert result["source_type"] == "custom"
    assert result["source_name"] == "自编练习题"
    assert result["is_favorited"] is True
    assert result["practice_count"] == 5
    # §6.3 不暴露敏感字段
    assert "created_by" not in result
    assert "status" not in result
    assert "updated_at" not in result


# ---------------------------------------------------------------------------
# favorite（questions.md §4）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favorite_non_published_returns_4001_to_prevent_probe() -> None:
    """非 published（draft/disabled）→ 4001/404（防探测，不区分，§4.3/§6.1）。"""
    db = _mock_db()
    # repo.get_published_question_by_id 对非 published 返回 None
    with patch("app.modules.questions.service.repo.get_published_question_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await question_service.favorite_question(db, 101, current_user=MagicMock(id=1))
    assert exc.value.code == 4001
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_favorite_new_adds_log_and_returns_true() -> None:
    """实际新增收藏 → 写 favorite_added 日志 + is_favorited=true。"""
    db = _mock_db()
    question = _make_question(qid=101, status="published")
    with (
        patch("app.modules.questions.service.repo.get_published_question_by_id", new=AsyncMock(return_value=question)),
        patch("app.modules.questions.service.repo.add_favorite", new=AsyncMock(return_value=True)),
    ):
        result = await question_service.favorite_question(db, 101, current_user=MagicMock(id=1))
    assert result["question_id"] == "101"
    assert result["is_favorited"] is True
    # 写了 1 条 favorite_added 日志
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert log_obj.action == "favorite_added"
    assert log_obj.entity_id == 101


@pytest.mark.asyncio
async def test_favorite_idempotent_no_log_returns_true() -> None:
    """重复收藏（幂等命中）→ 不写日志 + 仍返回 is_favorited=true。"""
    db = _mock_db()
    question = _make_question(qid=101, status="published")
    with (
        patch("app.modules.questions.service.repo.get_published_question_by_id", new=AsyncMock(return_value=question)),
        patch("app.modules.questions.service.repo.add_favorite", new=AsyncMock(return_value=False)),  # 冲突未插入
    ):
        result = await question_service.favorite_question(db, 101, current_user=MagicMock(id=1))
    assert result["is_favorited"] is True
    assert db.add.call_count == 0  # 幂等不写日志


# ---------------------------------------------------------------------------
# unfavorite（questions.md §5）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unfavorite_does_not_check_question_status() -> None:
    """取消收藏不校验题目状态（§5.3：无论题目是否存在/已收藏均成功）。"""
    db = _mock_db()
    # 不调用任何 get_question，直接 remove_favorite
    with patch("app.modules.questions.service.repo.remove_favorite", new=AsyncMock(return_value=False)):
        result = await question_service.unfavorite_question(db, 999, current_user=MagicMock(id=1))
    assert result["question_id"] == "999"
    assert result["is_favorited"] is False


@pytest.mark.asyncio
async def test_unfavorite_removed_writes_log_returns_false() -> None:
    """实际删除收藏 → 写 favorite_removed 日志 + is_favorited=false。"""
    db = _mock_db()
    with patch("app.modules.questions.service.repo.remove_favorite", new=AsyncMock(return_value=True)):
        result = await question_service.unfavorite_question(db, 101, current_user=MagicMock(id=1))
    assert result["is_favorited"] is False
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert log_obj.action == "favorite_removed"
    assert log_obj.entity_id == 101


@pytest.mark.asyncio
async def test_unfavorite_idempotent_no_log_returns_false() -> None:
    """重复取消（原本未收藏）→ 不写日志 + 仍返回 is_favorited=false。"""
    db = _mock_db()
    with patch("app.modules.questions.service.repo.remove_favorite", new=AsyncMock(return_value=False)):
        result = await question_service.unfavorite_question(db, 101, current_user=MagicMock(id=1))
    assert result["is_favorited"] is False
    assert db.add.call_count == 0


# ---------------------------------------------------------------------------
# router id 解析（questions.md §3.3/§4.3/§5.3 + §2.3）
# ---------------------------------------------------------------------------


def test_parse_question_id_invalid_raises_1001() -> None:
    """Path id 非法数字 → 1001/422。"""
    from app.modules.questions.router import _parse_question_id

    with pytest.raises(AppError) as exc:
        _parse_question_id("abc")
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


def test_parse_question_id_valid_returns_int() -> None:
    from app.modules.questions.router import _parse_question_id

    assert _parse_question_id("101") == 101


def test_parse_optional_id_none_returns_none() -> None:
    from app.modules.questions.router import _parse_optional_id

    assert _parse_optional_id(None) is None


def test_parse_optional_id_invalid_returns_minus1_for_empty_result() -> None:
    """Query 筛选 id 非法 → -1（不可能匹配真实 id → 空列表，§2.3 不报错）。"""
    from app.modules.questions.router import _parse_optional_id

    assert _parse_optional_id("abc") == -1
    assert _parse_optional_id("5") == 5
