"""Practice 模块测试（Phase 7.1-7.5）。

覆盖关键业务约束（practice.md）：
- create_session: mode 参数校验(1001) + topic 不存在(4003) + 题数不足(5004) + snapshot 生成 + activity_log
- get_session: 5001(不存在)/5003(越权) + 续练结构
- create_attempt: 5007(sq 不存在)/5003(越权)/5002(终态) + created→in_progress 激活 + attempt_number 递增
- update_attempt: submitted→1001 + 5005(不存在)/5003(越权)/5002(非进行中) + 状态机(5006) + skipped 写日志
- complete_session: ADR-015(5006 含 details) + 5002(非进行中) + 终态 + activity_log
- router: path id 非法→1001
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.models.practice import PracticeAttempt, PracticeSession, PracticeSessionQuestion
from app.models.question import SpeakingQuestion, SpeakingTopic
from app.modules.practice import service as practice_service

# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------


def _make_topic(*, tid: int = 5, name: str = "Technology") -> SpeakingTopic:
    return SpeakingTopic(
        id=tid,
        name=name,
        description="desc",
        sort_order=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_question(*, qid: int = 101, topic: SpeakingTopic | None = None) -> SpeakingQuestion:
    q = SpeakingQuestion(
        id=qid,
        part=2,
        topic_id=topic.id if topic else 5,
        title="Describe a useful object",
        content="Tell me about an object you use daily.",
        cue_card="You should say: what it is...",
        difficulty=3,
        status="published",
        source_type="custom",
        source_name="自编练习题",
        created_by=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    q.topic = topic or _make_topic()
    return q


def _make_session(
    *,
    sid: int = 201,
    user_id: int = 1,
    status: str = "created",
    started_at: datetime | None = None,
) -> PracticeSession:
    return PracticeSession(
        id=sid,
        user_id=user_id,
        mode="topic",
        part_filter=2,
        topic_filter=5,
        question_count=5,
        status=status,
        started_at=started_at,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_sq(*, sqid: int = 301, session_id: int = 201, question_id: int = 101) -> PracticeSessionQuestion:
    return PracticeSessionQuestion(
        id=sqid,
        session_id=session_id,
        question_id=question_id,
        question_snapshot={
            "part": 2,
            "title": "Describe a useful object",
            "content": "Tell me about an object you use daily.",
            "cue_card": "You should say: what it is...",
            "topic_name": "Technology",
            "difficulty": 3,
        },
        sort_order=1,
        created_at=datetime.now(UTC),
    )


def _make_attempt(
    *,
    aid: int = 401,
    sqid: int = 301,
    user_id: int = 1,
    attempt_number: int = 1,
    status: str = "pending",
) -> PracticeAttempt:
    return PracticeAttempt(
        id=aid,
        session_question_id=sqid,
        user_id=user_id,
        attempt_number=attempt_number,
        status=status,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# create_session（practice.md §2）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_topic_mode_missing_topic_id_returns_1001() -> None:
    """mode=topic 但 topic_id 缺失 → 1001/422。"""
    db = _mock_db()
    with pytest.raises(AppError) as exc:
        await practice_service.create_session(
            db,
            current_user=MagicMock(id=1),
            mode="topic",
            part=None,
            topic_id=None,
            question_count=5,
        )
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


@pytest.mark.asyncio
async def test_create_session_part_mode_missing_part_returns_1001() -> None:
    """mode=part 但 part 缺失 → 1001/422。"""
    db = _mock_db()
    with pytest.raises(AppError) as exc:
        await practice_service.create_session(
            db,
            current_user=MagicMock(id=1),
            mode="part",
            part=None,
            topic_id=None,
            question_count=5,
        )
    assert exc.value.code == 1001


@pytest.mark.asyncio
async def test_create_session_topic_not_found_returns_4003() -> None:
    """mode=topic 但 topic 不存在 → 4003/404。"""
    db = _mock_db()
    with patch("app.modules.practice.service.repo.get_topic_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await practice_service.create_session(
                db,
                current_user=MagicMock(id=1),
                mode="topic",
                part=None,
                topic_id="999",
                question_count=5,
            )
    assert exc.value.code == 4003
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_create_session_insufficient_questions_returns_5004() -> None:
    """可用题数 < question_count → 5004/400。"""
    db = _mock_db()
    topic = _make_topic()
    with (
        patch("app.modules.practice.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.practice.service.repo.count_available_questions", new=AsyncMock(return_value=3)),
    ):
        with pytest.raises(AppError) as exc:
            await practice_service.create_session(
                db,
                current_user=MagicMock(id=1),
                mode="topic",
                part=None,
                topic_id="5",
                question_count=5,
            )
    assert exc.value.code == 5004
    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_create_session_success_builds_snapshots_and_logs() -> None:
    """成功创建 → snapshot 生成 + activity_log(practice_started) + attempts=[]。"""
    db = _mock_db()
    topic = _make_topic()
    q1 = _make_question(qid=101, topic=topic)
    q2 = _make_question(qid=102, topic=topic)
    session = _make_session(sid=201, status="created")
    sq1 = _make_sq(sqid=301, question_id=101)
    sq2 = _make_sq(sqid=302, question_id=102)

    with (
        patch("app.modules.practice.service.repo.get_topic_by_id", new=AsyncMock(return_value=topic)),
        patch("app.modules.practice.service.repo.count_available_questions", new=AsyncMock(return_value=10)),
        patch("app.modules.practice.service.repo.sample_published_questions", new=AsyncMock(return_value=[q1, q2])),
        patch("app.modules.practice.service.repo.insert_session", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.insert_session_questions", new=AsyncMock(return_value=[sq1, sq2])),
    ):
        result = await practice_service.create_session(
            db,
            current_user=MagicMock(id=1),
            mode="topic",
            part=None,
            topic_id="5",
            question_count=2,
        )
    assert result["id"] == "201"
    assert result["status"] == "created"
    assert result["mode"] == "topic"
    assert result["topic_filter"] == "5"
    assert len(result["questions"]) == 2
    assert result["questions"][0]["snapshot"]["topic_name"] == "Technology"
    assert result["questions"][0]["attempts"] == []
    # 写了 practice_started 日志
    assert db.add.call_count == 1
    log_obj = db.add.call_args.args[0]
    assert log_obj.action == "practice_started"
    assert log_obj.entity_id == 201


# ---------------------------------------------------------------------------
# get_session（practice.md §3）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_not_found_returns_5001() -> None:
    """会话不存在 → 5001/404。"""
    db = _mock_db()
    with patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await practice_service.get_session(db, 999, current_user=MagicMock(id=1))
    assert exc.value.code == 5001
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_get_session_wrong_user_returns_5003() -> None:
    """越权访问 → 5003/403。"""
    db = _mock_db()
    session = _make_session(sid=201, user_id=1)
    with patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)):
        with pytest.raises(AppError) as exc:
            await practice_service.get_session(db, 201, current_user=MagicMock(id=2))
    assert exc.value.code == 5003
    assert exc.value.http_status == 403


@pytest.mark.asyncio
async def test_get_session_returns_questions_with_attempts() -> None:
    """成功 → 返回 questions + attempts（含 recording=None）。"""
    db = _mock_db()
    session = _make_session(sid=201, user_id=1, status="in_progress")
    sq = _make_sq(sqid=301)
    attempt = _make_attempt(aid=401, sqid=301, status="recording")
    with (
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.get_session_questions", new=AsyncMock(return_value=[sq])),
        patch("app.modules.practice.service.repo.get_attempts_for_sqs", new=AsyncMock(return_value={301: [(attempt, None)]})),
    ):
        result = await practice_service.get_session(db, 201, current_user=MagicMock(id=1))
    assert result["status"] == "in_progress"
    assert len(result["questions"]) == 1
    assert result["questions"][0]["attempts"][0]["status"] == "recording"
    assert result["questions"][0]["attempts"][0]["recording"] is None


# ---------------------------------------------------------------------------
# create_attempt（practice.md §4）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_attempt_sq_not_found_returns_5007() -> None:
    """session_question 不存在 → 5007/404。"""
    db = _mock_db()
    with patch("app.modules.practice.service.repo.get_session_question_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await practice_service.create_attempt(
                db, current_user=MagicMock(id=1), session_question_id="999"
            )
    assert exc.value.code == 5007
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_create_attempt_wrong_user_returns_5003() -> None:
    """越权 → 5003/403。"""
    db = _mock_db()
    sq = _make_sq(sqid=301, session_id=201)
    session = _make_session(sid=201, user_id=1)
    with (
        patch("app.modules.practice.service.repo.get_session_question_by_id", new=AsyncMock(return_value=sq)),
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
    ):
        with pytest.raises(AppError) as exc:
            await practice_service.create_attempt(
                db, current_user=MagicMock(id=2), session_question_id="301"
            )
    assert exc.value.code == 5003


@pytest.mark.asyncio
async def test_create_attempt_terminal_session_returns_5002() -> None:
    """会话终态（completed）→ 5002/400。"""
    db = _mock_db()
    sq = _make_sq(sqid=301, session_id=201)
    session = _make_session(sid=201, user_id=1, status="completed")
    with (
        patch("app.modules.practice.service.repo.get_session_question_by_id", new=AsyncMock(return_value=sq)),
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
    ):
        with pytest.raises(AppError) as exc:
            await practice_service.create_attempt(
                db, current_user=MagicMock(id=1), session_question_id="301"
            )
    assert exc.value.code == 5002
    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_create_attempt_activates_created_session() -> None:
    """created → 激活 in_progress（调 activate_session）+ attempt_number 递增。"""
    db = _mock_db()
    sq = _make_sq(sqid=301, session_id=201)
    session = _make_session(sid=201, user_id=1, status="created")
    attempt = _make_attempt(aid=401, sqid=301, attempt_number=1, status="pending")
    with (
        patch("app.modules.practice.service.repo.get_session_question_by_id", new=AsyncMock(return_value=sq)),
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.activate_session", new=AsyncMock()) as activate_mock,
        patch("app.modules.practice.service.repo.next_attempt_number", new=AsyncMock(return_value=1)),
        patch("app.modules.practice.service.repo.insert_attempt", new=AsyncMock(return_value=attempt)),
    ):
        result = await practice_service.create_attempt(
            db, current_user=MagicMock(id=1), session_question_id="301"
        )
    activate_mock.assert_awaited_once_with(db, 201)
    assert result["attempt_number"] == 1
    assert result["status"] == "pending"
    assert result["recording"] is None
    # 写了 attempt_created 日志
    assert db.add.call_count == 1
    assert db.add.call_args.args[0].action == "attempt_created"


@pytest.mark.asyncio
async def test_create_attempt_in_progress_no_reactivate() -> None:
    """in_progress → 不再激活（activate_session 不调用）。"""
    db = _mock_db()
    sq = _make_sq(sqid=301, session_id=201)
    session = _make_session(sid=201, user_id=1, status="in_progress")
    attempt = _make_attempt(aid=402, sqid=301, attempt_number=2, status="pending")
    with (
        patch("app.modules.practice.service.repo.get_session_question_by_id", new=AsyncMock(return_value=sq)),
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.activate_session", new=AsyncMock()) as activate_mock,
        patch("app.modules.practice.service.repo.next_attempt_number", new=AsyncMock(return_value=2)),
        patch("app.modules.practice.service.repo.insert_attempt", new=AsyncMock(return_value=attempt)),
    ):
        result = await practice_service.create_attempt(
            db, current_user=MagicMock(id=1), session_question_id="301"
        )
    activate_mock.assert_not_awaited()
    assert result["attempt_number"] == 2


# ---------------------------------------------------------------------------
# update_attempt（practice.md §5）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_attempt_submitted_returns_1001() -> None:
    """传 submitted → 1001（必须走录音上传接口，ADR-015）。"""
    db = _mock_db()
    with pytest.raises(AppError) as exc:
        await practice_service.update_attempt(
            db, 401, current_user=MagicMock(id=1), target_status="submitted"
        )
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


@pytest.mark.asyncio
async def test_update_attempt_not_found_returns_5005() -> None:
    """attempt 不存在 → 5005/404。"""
    db = _mock_db()
    with patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await practice_service.update_attempt(
                db, 999, current_user=MagicMock(id=1), target_status="recording"
            )
    assert exc.value.code == 5005
    assert exc.value.http_status == 404


@pytest.mark.asyncio
async def test_update_attempt_wrong_user_returns_5003() -> None:
    """越权 → 5003/403。"""
    db = _mock_db()
    attempt = _make_attempt(aid=401, user_id=1)
    with patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=attempt)):
        with pytest.raises(AppError) as exc:
            await practice_service.update_attempt(
                db, 401, current_user=MagicMock(id=2), target_status="recording"
            )
    assert exc.value.code == 5003


@pytest.mark.asyncio
async def test_update_attempt_session_not_in_progress_returns_5002() -> None:
    """session 非 in_progress → 5002/400。"""
    db = _mock_db()
    attempt = _make_attempt(aid=401, user_id=1)
    session = _make_session(sid=201, user_id=1, status="completed")
    with (
        patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=attempt)),
        patch("app.modules.practice.service.repo.get_session_of_attempt", new=AsyncMock(return_value=session)),
    ):
        with pytest.raises(AppError) as exc:
            await practice_service.update_attempt(
                db, 401, current_user=MagicMock(id=1), target_status="recording"
            )
    assert exc.value.code == 5002


@pytest.mark.asyncio
async def test_update_attempt_invalid_transition_returns_5006() -> None:
    """非法状态转换（pending→failed）→ 5006/400。"""
    db = _mock_db()
    attempt = _make_attempt(aid=401, user_id=1, status="pending")
    session = _make_session(sid=201, user_id=1, status="in_progress")
    with (
        patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=attempt)),
        patch("app.modules.practice.service.repo.get_session_of_attempt", new=AsyncMock(return_value=session)),
    ):
        with pytest.raises(AppError) as exc:
            await practice_service.update_attempt(
                db, 401, current_user=MagicMock(id=1), target_status="failed"
            )
    assert exc.value.code == 5006
    assert exc.value.http_status == 400


@pytest.mark.asyncio
async def test_update_attempt_pending_to_recording_success() -> None:
    """pending → recording ✅（合法转换，填 started_at）。"""
    db = _mock_db()
    attempt = _make_attempt(aid=401, user_id=1, status="pending")
    session = _make_session(sid=201, user_id=1, status="in_progress")

    async def _mutate(_db, att, *, target_status):
        att.status = target_status

    with (
        patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=attempt)),
        patch("app.modules.practice.service.repo.get_session_of_attempt", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.update_attempt_status", new=AsyncMock(side_effect=_mutate)) as update_mock,
    ):
        result = await practice_service.update_attempt(
            db, 401, current_user=MagicMock(id=1), target_status="recording"
        )
    update_mock.assert_awaited_once()
    assert result["status"] == "recording"
    # recording 转换不写 activity_log
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_update_attempt_to_skipped_writes_log() -> None:
    """→ skipped 写 attempt_skipped 日志。"""
    db = _mock_db()
    attempt = _make_attempt(aid=401, user_id=1, status="pending")
    session = _make_session(sid=201, user_id=1, status="in_progress")
    with (
        patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=attempt)),
        patch("app.modules.practice.service.repo.get_session_of_attempt", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.update_attempt_status", new=AsyncMock()),
    ):
        await practice_service.update_attempt(
            db, 401, current_user=MagicMock(id=1), target_status="skipped"
        )
    assert db.add.call_count == 1
    assert db.add.call_args.args[0].action == "attempt_skipped"


@pytest.mark.asyncio
async def test_update_attempt_recording_to_failed_success() -> None:
    """recording → failed ✅（合法转换）。"""
    db = _mock_db()
    attempt = _make_attempt(aid=401, user_id=1, status="recording")
    session = _make_session(sid=201, user_id=1, status="in_progress")

    async def _mutate(_db, att, *, target_status):
        att.status = target_status

    with (
        patch("app.modules.practice.service.repo.get_attempt_by_id", new=AsyncMock(return_value=attempt)),
        patch("app.modules.practice.service.repo.get_session_of_attempt", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.update_attempt_status", new=AsyncMock(side_effect=_mutate)),
    ):
        result = await practice_service.update_attempt(
            db, 401, current_user=MagicMock(id=1), target_status="failed"
        )
    assert result["status"] == "failed"
    assert db.add.call_count == 0  # failed 不写日志


# ---------------------------------------------------------------------------
# complete_session（practice.md §8）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_session_not_found_returns_5001() -> None:
    """会话不存在 → 5001/404。"""
    db = _mock_db()
    with patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(AppError) as exc:
            await practice_service.complete_session(db, 999, current_user=MagicMock(id=1))
    assert exc.value.code == 5001


@pytest.mark.asyncio
async def test_complete_session_wrong_user_returns_5003() -> None:
    """越权 → 5003/403。"""
    db = _mock_db()
    session = _make_session(sid=201, user_id=1, status="in_progress")
    with patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)):
        with pytest.raises(AppError) as exc:
            await practice_service.complete_session(db, 201, current_user=MagicMock(id=2))
    assert exc.value.code == 5003


@pytest.mark.asyncio
async def test_complete_session_not_in_progress_returns_5002() -> None:
    """非 in_progress（created）→ 5002/400。"""
    db = _mock_db()
    session = _make_session(sid=201, user_id=1, status="created")
    with patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)):
        with pytest.raises(AppError) as exc:
            await practice_service.complete_session(db, 201, current_user=MagicMock(id=1))
    assert exc.value.code == 5002


@pytest.mark.asyncio
async def test_complete_session_adr015_violation_returns_5006_with_details() -> None:
    """ADR-015 违反：存在 sq 无 submitted/skipped → 5006 含 details。"""
    db = _mock_db()
    session = _make_session(sid=201, user_id=1, status="in_progress")
    sq1 = _make_sq(sqid=301, question_id=101)
    sq2 = _make_sq(sqid=302, question_id=102)
    sq2.sort_order = 2
    # sq1 有 submitted，sq2 无任何 attempt（status 集合为空）
    summary = {301: {"submitted"}, 302: set()}
    with (
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.get_session_questions", new=AsyncMock(return_value=[sq1, sq2])),
        patch("app.modules.practice.service.repo.get_attempt_status_summary", new=AsyncMock(return_value=summary)),
    ):
        with pytest.raises(AppError) as exc:
            await practice_service.complete_session(db, 201, current_user=MagicMock(id=1))
    assert exc.value.code == 5006
    assert exc.value.http_status == 400
    # details 含未完成的 sq_id 列表
    assert exc.value.details is not None
    incomplete_ids = [d["session_question_id"] for d in exc.value.details]
    assert "302" in incomplete_ids
    assert "301" not in incomplete_ids


@pytest.mark.asyncio
async def test_complete_session_success_returns_completed_with_duration() -> None:
    """ADR-015 通过 → status=completed + duration_seconds + activity_log。"""
    db = _mock_db()
    started = datetime.now(UTC)
    session = _make_session(sid=201, user_id=1, status="in_progress", started_at=started)
    sq = _make_sq(sqid=301, question_id=101)
    attempt = _make_attempt(aid=401, sqid=301, status="submitted")
    summary = {301: {"submitted"}}

    async def _complete(_db, sess):
        sess.status = "completed"
        sess.completed_at = datetime.now(UTC)
        sess.duration_seconds = 100

    with (
        patch("app.modules.practice.service.repo.get_session_by_id", new=AsyncMock(return_value=session)),
        patch("app.modules.practice.service.repo.get_session_questions", new=AsyncMock(return_value=[sq])),
        patch("app.modules.practice.service.repo.get_attempt_status_summary", new=AsyncMock(return_value=summary)),
        patch("app.modules.practice.service.repo.complete_session", new=AsyncMock(side_effect=_complete)) as complete_mock,
        patch("app.modules.practice.service.repo.get_attempts_for_sqs", new=AsyncMock(return_value={301: [(attempt, None)]})),
    ):
        result = await practice_service.complete_session(db, 201, current_user=MagicMock(id=1))
    complete_mock.assert_awaited_once()
    assert result["status"] == "completed"
    assert result["duration_seconds"] == 100
    assert db.add.call_count == 1
    assert db.add.call_args.args[0].action == "practice_completed"


# ---------------------------------------------------------------------------
# router id 解析（practice.md §3.3/§8.3）
# ---------------------------------------------------------------------------


def test_parse_path_id_invalid_raises_1001() -> None:
    """Path id 非法数字 → 1001/422。"""
    from app.modules.practice.router import _parse_path_id

    with pytest.raises(AppError) as exc:
        _parse_path_id("abc", field="session_id")
    assert exc.value.code == 1001
    assert exc.value.http_status == 422


def test_parse_path_id_valid_returns_int() -> None:
    from app.modules.practice.router import _parse_path_id

    assert _parse_path_id("201", field="session_id") == 201


# ---------------------------------------------------------------------------
# 状态机转换矩阵（practice.md §5.3）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current,target,should_pass",
    [
        ("pending", "recording", True),
        ("pending", "skipped", True),
        ("pending", "failed", False),
        ("recording", "skipped", True),
        ("recording", "failed", True),
        ("recording", "recording", False),
        ("submitted", "recording", False),
        ("skipped", "recording", False),
        ("failed", "recording", False),
    ],
)
def test_validate_transition_matrix(current: str, target: str, should_pass: bool) -> None:
    """状态机转换矩阵全覆盖（practice.md §5.3）。"""
    if should_pass:
        practice_service._validate_transition(current, target)
    else:
        with pytest.raises(AppError) as exc:
            practice_service._validate_transition(current, target)
        assert exc.value.code == 5006
