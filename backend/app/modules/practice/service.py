"""Practice 模块业务逻辑（system-architecture §3：service 层）。

对齐 practice.md §2/§3/§4/§5/§6/§7/§8：
- 创建会话：mode 校验 + topic 存在(4003) + 题数不足(5004) + 随机抽题 + snapshot
- 获取会话：5001(不存在)/5003(越权) + 续练可用
- 创建 attempt：session_question(5007) + 所有权(5003) + 激活 session(created→in_progress) + 5002(终态)
- 更新 attempt：submitted→1001 + 所有权(5003) + session in_progress(5002) + 状态机(5006)
- 录音上传：5005/5003/5006/6003/6004/6002 + 事务(recording.uploaded→attempt.submitted→study_records)
- 录音下载：5005/5003/6001 + StreamingResponse
- 完成会话：ADR-015(每 sq 有 submitted/skipped) → 5006 + 终态(5002) + study_records.practice_count++
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audio import AudioMetadataError, read_duration_seconds
from app.core.exceptions import AppError
from app.core.storage import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    AudioStorage,
    cleanup_storage_on_failure,
)
from app.models.activity import UserActivityLog
from app.models.practice import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionQuestion,
    Recording,
)
from app.models.user import User
from app.modules.practice import repository as repo
from app.modules.practice.schemas import (
    AttemptDTO,
    PracticeSessionDTO,
    RecordingDTO,
    SessionQuestionDTO,
)

# 会话状态（practice.md §2.2）
_SESSION_CREATED = "created"
_SESSION_IN_PROGRESS = "in_progress"
_SESSION_TERMINAL = {"completed", "abandoned", "expired"}

# 合法状态转换（practice.md §5.3）
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"recording", "skipped"},
    "recording": {"skipped", "failed"},
}


# ---------------------------------------------------------------------------
# DTO 组装
# ---------------------------------------------------------------------------


def _build_recording(recording: Recording | None) -> RecordingDTO | None:
    """构造 RecordingDTO（Phase 7 恒为 None，Phase 8 录音上传后非空）。"""
    if recording is None or recording.status == "deleted":
        return None
    return RecordingDTO(
        id=str(recording.id),
        status=recording.status,
        mime_type=recording.mime_type,
        duration_seconds=recording.duration_seconds,
        file_size=recording.file_size,
        created_at=recording.created_at,
    )


def _build_attempt(
    attempt: PracticeAttempt, recording: Recording | None
) -> AttemptDTO:
    """构造 AttemptDTO（practice.md §3.2）。"""
    return AttemptDTO(
        id=str(attempt.id),
        session_question_id=str(attempt.session_question_id),
        attempt_number=attempt.attempt_number,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        duration_seconds=attempt.duration_seconds,
        recording=_build_recording(recording),
    )


def _build_session(
    session: PracticeSession,
    sqs: list[PracticeSessionQuestion],
    attempts_map: dict[int, list[tuple[PracticeAttempt, Recording | None]]],
) -> PracticeSessionDTO:
    """构造 PracticeSessionDTO（practice.md §2.2）。"""
    questions = [
        SessionQuestionDTO(
            id=str(sq.id),
            session_id=str(sq.session_id),
            question_id=str(sq.question_id),
            sort_order=sq.sort_order,
            snapshot=sq.question_snapshot,
            attempts=[
                _build_attempt(a, r)
                for a, r in attempts_map.get(sq.id, [])
            ],
        )
        for sq in sqs
    ]
    return PracticeSessionDTO(
        id=str(session.id),
        status=session.status,
        mode=session.mode,
        part_filter=session.part_filter,
        topic_filter=str(session.topic_filter) if session.topic_filter is not None else None,
        question_count=session.question_count,
        started_at=session.started_at,
        completed_at=session.completed_at,
        duration_seconds=session.duration_seconds,
        created_at=session.created_at,
        updated_at=session.updated_at,
        questions=questions,
    )


def _session_to_dict(session_dto: PracticeSessionDTO) -> dict[str, Any]:
    return session_dto.model_dump(mode="json")


def _attempt_to_dict(attempt: PracticeAttempt, recording: Recording | None) -> dict[str, Any]:
    return _build_attempt(attempt, recording).model_dump(mode="json")


# ---------------------------------------------------------------------------
# 创建会话（practice.md §2）
# ---------------------------------------------------------------------------


def _parse_topic_id(raw: str | None) -> int | None:
    """topic_id 字符串转 int；None → None，非合法数字 → None（后续查不到→4003）。"""
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def create_session(
    db: AsyncSession,
    *,
    current_user: User,
    mode: str,
    part: int | None,
    topic_id: str | None,
    question_count: int,
) -> dict[str, Any]:
    """创建练习会话（practice.md §2.4）。

    mode 语义（§2.1）：
    - random：全题库随机抽（part/topic 可选叠加）
    - topic：指定 topic_id 抽（part 可选叠加），topic_id 必填
    - part：指定 part 抽（topic_id 不传），part 必填
    """
    topic_id_int = _parse_topic_id(topic_id)
    _validate_mode_params(mode, part=part, topic_id=topic_id, topic_id_int=topic_id_int)

    # mode=topic：校验 topic 存在（§2.4 step 2）→ 不存在 → 4003
    if mode == "topic":
        topic = await repo.get_topic_by_id(db, topic_id_int)  # type: ignore[arg-type]
        if topic is None:
            raise AppError(code=4003, message="主题不存在", http_status=404)

    # 统计可用题数（§2.4 step 4）→ 不足 → 5004
    available = await repo.count_available_questions(
        db, part=part, topic_id=topic_id_int if mode != "part" else None
    )
    if available < question_count:
        raise AppError(
            code=5004,
            message=f"题目数量不足，可用 {available} 题，需要 {question_count} 题",
            http_status=400,
        )

    # 随机抽题（§2.4 step 5）
    questions = await repo.sample_published_questions(
        db,
        count=question_count,
        part=part,
        topic_id=topic_id_int if mode != "part" else None,
    )

    # 事务内：INSERT session + sq(snapshots) + activity_log（§2.4 step 6）
    session = await repo.insert_session(
        db,
        user_id=current_user.id,
        mode=mode,
        part_filter=part,
        topic_filter=topic_id_int if mode != "part" else None,
        question_count=question_count,
    )
    sqs = await repo.insert_session_questions(
        db, session_id=session.id, questions=questions
    )

    log = UserActivityLog(
        user_id=current_user.id,
        action="practice_started",
        entity_type="practice_session",
        entity_id=session.id,
    )
    db.add(log)
    await db.flush()

    # 返回完整 PracticeSession（questions 含 attempts=[]，§2.4 step 7）
    session_dto = _build_session(session, sqs, attempts_map={})
    return _session_to_dict(session_dto)


def _validate_mode_params(
    mode: str,
    *,
    part: int | None,
    topic_id: str | None,
    topic_id_int: int | None,
) -> None:
    """校验 mode 与参数匹配（practice.md §2.1/§2.3）。

    - mode=topic：topic_id 必填（None 或非合法数字 → 1001）
    - mode=part：part 必填（None → 1001）
    """
    if mode == "topic" and topic_id_int is None:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "topic_id", "message": "mode=topic 时 topic_id 必填"}],
        )
    if mode == "part" and part is None:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "part", "message": "mode=part 时 part 必填"}],
        )


# ---------------------------------------------------------------------------
# 获取会话（practice.md §3）
# ---------------------------------------------------------------------------


async def get_session(
    db: AsyncSession, session_id: int, *, current_user: User
) -> dict[str, Any]:
    """获取会话详情（practice.md §3.4，含题目快照与 attempts）。

    - 不存在 → 5001/404
    - 越权 → 5003/403
    """
    session = await repo.get_session_by_id(db, session_id)
    if session is None:
        raise AppError(code=5001, message="会话不存在", http_status=404)
    if session.user_id != current_user.id:
        raise AppError(code=5003, message="无权访问该会话", http_status=403)

    sqs = await repo.get_session_questions(db, session_id)
    attempts_map = await repo.get_attempts_for_sqs(db, [sq.id for sq in sqs])
    session_dto = _build_session(session, sqs, attempts_map)
    return _session_to_dict(session_dto)


# ---------------------------------------------------------------------------
# 创建 attempt（practice.md §4）
# ---------------------------------------------------------------------------


async def create_attempt(
    db: AsyncSession,
    *,
    current_user: User,
    session_question_id: str,
) -> dict[str, Any]:
    """创建答题尝试（practice.md §4.4）。

    - session_question 不存在 → 5007/404
    - 会话不存在 → 5001/404；越权 → 5003/403
    - 会话终态（completed/abandoned/expired）→ 5002/400
    - created → 自动激活 in_progress（§4.4 step 3）
    """
    sq_id = _parse_path_id(session_question_id, field="session_question_id")
    sq = await repo.get_session_question_by_id(db, sq_id)
    if sq is None:
        raise AppError(code=5007, message="会话题目不存在", http_status=404)

    session = await repo.get_session_by_id(db, sq.session_id)
    if session is None:
        raise AppError(code=5001, message="会话不存在", http_status=404)
    if session.user_id != current_user.id:
        raise AppError(code=5003, message="无权操作该会话", http_status=403)

    # 会话状态校验（§4.4 step 3）
    if session.status in _SESSION_TERMINAL:
        raise AppError(
            code=5002,
            message="会话已结束，无法创建答题尝试",
            http_status=400,
        )
    # created → 激活 in_progress
    if session.status == _SESSION_CREATED:
        await repo.activate_session(db, session.id)

    # attempt_number = MAX+1（§4.4 step 4）
    attempt_number = await repo.next_attempt_number(db, sq_id)
    attempt = await repo.insert_attempt(
        db,
        session_question_id=sq_id,
        user_id=current_user.id,
        attempt_number=attempt_number,
    )

    log = UserActivityLog(
        user_id=current_user.id,
        action="attempt_created",
        entity_type="practice_attempt",
        entity_id=attempt.id,
    )
    db.add(log)
    await db.flush()

    return _attempt_to_dict(attempt, recording=None)


# ---------------------------------------------------------------------------
# 更新 attempt（practice.md §5）
# ---------------------------------------------------------------------------


async def update_attempt(
    db: AsyncSession,
    attempt_id: int,
    *,
    current_user: User,
    target_status: str,
) -> dict[str, Any]:
    """更新答题状态（practice.md §5.5）。

    - submitted → 1001（必须走录音上传接口，ADR-015）
    - attempt 不存在 → 5005/404；越权 → 5003/403
    - session 非 in_progress → 5002/400
    - 状态转换非法 → 5006/400
    """
    # submitted 不可前端直设（§5.1/§5.3）
    if target_status == "submitted":
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[
                {
                    "field": "status",
                    "message": "submitted 只能由录音上传接口设置",
                }
            ],
        )

    attempt = await repo.get_attempt_by_id(db, attempt_id)
    if attempt is None:
        raise AppError(code=5005, message="答题尝试不存在", http_status=404)
    if attempt.user_id != current_user.id:
        raise AppError(code=5003, message="无权操作该答题尝试", http_status=403)

    # 间接校验 session 状态（§5.5 step 3）
    session = await repo.get_session_of_attempt(db, attempt)
    if session is None:
        raise AppError(code=5001, message="会话不存在", http_status=404)
    if session.status != _SESSION_IN_PROGRESS:
        raise AppError(
            code=5002,
            message="会话不在进行中，无法更新答题状态",
            http_status=400,
        )

    # 状态转换合法性（§5.3）
    _validate_transition(attempt.status, target_status)

    # 事务内：UPDATE + activity_log（skipped 记日志，§5.5 step 5）
    await repo.update_attempt_status(db, attempt, target_status=target_status)
    if target_status == "skipped":
        log = UserActivityLog(
            user_id=current_user.id,
            action="attempt_skipped",
            entity_type="practice_attempt",
            entity_id=attempt.id,
        )
        db.add(log)
        await db.flush()

    return _attempt_to_dict(attempt, recording=None)


def _validate_transition(current: str, target: str) -> None:
    """校验状态转换合法性（practice.md §5.3）。

    pending → recording ✅
    pending → skipped ✅
    recording → skipped ✅
    recording → failed ✅
    其他 → 5006
    """
    allowed = _VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise AppError(
            code=5006,
            message=f"非法状态转换：{current} → {target}",
            http_status=400,
        )


# ---------------------------------------------------------------------------
# 完成会话（practice.md §8）
# ---------------------------------------------------------------------------


async def complete_session(
    db: AsyncSession, session_id: int, *, current_user: User
) -> dict[str, Any]:
    """完成会话（practice.md §8.4）。

    - 不存在 → 5001/404；越权 → 5003/403
    - 非 in_progress → 5002/400（created 需先创建 attempt 激活）
    - ADR-015 违反：存在 sq 无 submitted/skipped attempt → 5006/400（含 details）
    - study_records.practice_count++ 留待 Phase 8.5（ADR-022）
    """
    session = await repo.get_session_by_id(db, session_id)
    if session is None:
        raise AppError(code=5001, message="会话不存在", http_status=404)
    if session.user_id != current_user.id:
        raise AppError(code=5003, message="无权操作该会话", http_status=403)
    if session.status != _SESSION_IN_PROGRESS:
        raise AppError(
            code=5002,
            message="会话不在进行中，无法完成",
            http_status=400,
        )

    # ADR-015 校验：每个 sq 至少有一个 submitted/skipped attempt（§8.4 step 4）
    sqs = await repo.get_session_questions(db, session_id)
    status_summary = await repo.get_attempt_status_summary(db, session_id)
    incomplete: list[dict[str, Any]] = []
    for sq in sqs:
        statuses = status_summary.get(sq.id, set())
        if not (statuses & {"submitted", "skipped"}):
            incomplete.append({"session_question_id": str(sq.id), "sort_order": sq.sort_order})
    if incomplete:
        raise AppError(
            code=5006,
            message="存在未完成的题目，无法完成会话",
            http_status=400,
            details=incomplete,
        )

    # 事务内：UPDATE session 终态 + study_records + activity_log（§8.4 step 5，ADR-022）
    await repo.complete_session(db, session)

    # study_records.practice_count += 1（ADR-022 同步更新）
    tz = await repo.get_user_timezone(db, current_user.id)
    record_date = repo.compute_record_date(datetime.now(UTC), tz)
    await repo.upsert_study_record_for_session_complete(
        db, user_id=current_user.id, record_date=record_date
    )

    log = UserActivityLog(
        user_id=current_user.id,
        action="practice_completed",
        entity_type="practice_session",
        entity_id=session.id,
    )
    db.add(log)
    await db.flush()

    # 返回完整 PracticeSession（含 questions + attempts）
    attempts_map = await repo.get_attempts_for_sqs(db, [sq.id for sq in sqs])
    session_dto = _build_session(session, sqs, attempts_map)
    return _session_to_dict(session_dto)


# ---------------------------------------------------------------------------
# 录音上传（practice.md §6，Phase 8）
# ---------------------------------------------------------------------------


async def upload_recording(
    db: AsyncSession,
    attempt_id: int,
    *,
    current_user: User,
    file_data: bytes,
    mime_type: str,
    file_size: int,
    storage: AudioStorage,
) -> dict[str, Any]:
    """上传录音（practice.md §6.4，严格对齐 §5.1 序列图 + ADR-015）。

    事务内顺序：写文件 → 读元数据 → INSERT recording(uploading)
    → UPDATE recording(uploaded) → UPDATE attempt(submitted) → upsert study_records → log
    任一失败全回滚（文件清理 + recording 标 failed）。

    错误码：5005/5003/5006/6003/6004/6002。
    """
    # 1. 查 attempt → 5005（practice.md §6.4 step 1）
    attempt = await repo.get_attempt_by_id(db, attempt_id)
    if attempt is None:
        raise AppError(code=5005, message="答题尝试不存在", http_status=404)
    # 2. 所有权 → 5003（§6.4 step 2）
    if attempt.user_id != current_user.id:
        raise AppError(code=5003, message="无权操作该答题尝试", http_status=403)
    # 3. status ∈ {pending, recording} → 5006（§6.4 step 3）
    if attempt.status not in {"pending", "recording"}:
        raise AppError(
            code=5006,
            message=f"当前状态 {attempt.status} 不可上传录音，请新建答题尝试",
            http_status=400,
        )
    # 4. 校验文件：mime_type 白名单 → 6003；file_size ≤ 50MB → 6004（§6.4 step 4）
    if mime_type not in ALLOWED_MIME_TYPES:
        raise AppError(
            code=6003,
            message=f"不支持的音频格式：{mime_type}",
            http_status=400,
        )
    if file_size > MAX_FILE_SIZE:
        raise AppError(
            code=6004,
            message=f"文件过大：{file_size} 字节，超过限制 {MAX_FILE_SIZE} 字节",
            http_status=413,
        )

    # 5. 事务内：写文件 → 读元数据 → INSERT/UPDATE recording → UPDATE attempt → study_records
    storage_path: str | None = None
    recording: Recording | None = None
    try:
        # 5a. 写文件到存储（§6.4 step 5a）
        storage_path = storage.save(file_data, mime_type=mime_type)

        # 5b. 读音频元数据 → duration_seconds（ADR-020，§6.4 step 5b）
        # 失败 → 删除文件 + 6002
        try:
            duration_seconds = read_duration_seconds(file_data, mime_type=mime_type)
        except AudioMetadataError:
            cleanup_storage_on_failure(storage, storage_path)
            storage_path = None
            raise AppError(
                code=6002,
                message="音频元数据读取失败",
                http_status=400,
            ) from None

        # 5c. INSERT recordings(status='uploading')（§6.4 step 5c）
        storage_type = "s3" if storage.__class__.__name__ == "S3StorageBackend" else "local"
        recording = await repo.insert_recording(
            db,
            attempt_id=attempt.id,
            user_id=current_user.id,
            storage_type=storage_type,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
        )

        # 5d. UPDATE recordings SET status='uploaded' + duration（§6.4 step 5d）
        await repo.mark_recording_uploaded(
            db, recording, duration_seconds=duration_seconds
        )

        # 5e. UPDATE attempts SET status='submitted' + duration（ADR-015，§6.4 step 5e）
        # submitted 前置 recording.uploaded 已满足
        await repo.submit_attempt_with_recording(
            db, attempt, duration_seconds=duration_seconds
        )

        # 5f. UPSERT study_records（ADR-022 同步更新，§6.4 step 5f）
        tz = await repo.get_user_timezone(db, current_user.id)
        record_date = repo.compute_record_date(datetime.now(UTC), tz)
        await repo.upsert_study_record_for_recording(
            db,
            user_id=current_user.id,
            record_date=record_date,
            duration_seconds=duration_seconds,
        )

        # 5g. INSERT user_activity_logs（§6.4 step 5g）
        log = UserActivityLog(
            user_id=current_user.id,
            action="recording_uploaded",
            entity_type="recording",
            entity_id=recording.id,
            metadata_={"duration_seconds": duration_seconds, "file_size": file_size},
        )
        db.add(log)
        await db.flush()

        return _attempt_to_dict(attempt, recording)

    except AppError:
        raise
    except Exception:
        # 事务回滚：清理已写文件 + recording 标 failed（§6.4 事务边界说明）
        cleanup_storage_on_failure(storage, storage_path)
        if recording is not None:
            try:
                await repo.mark_recording_failed(db, recording)
            except Exception:
                pass
        raise AppError(
            code=6002,
            message="录音上传失败",
            http_status=400,
        ) from None


# ---------------------------------------------------------------------------
# 录音下载（practice.md §7，Phase 8）
# ---------------------------------------------------------------------------


async def download_recording(
    db: AsyncSession,
    attempt_id: int,
    *,
    current_user: User,
    storage: AudioStorage,
) -> tuple[Recording, bytes]:
    """下载录音（practice.md §7.4）。

    返回 (recording, file_bytes)，由 router 层构造 StreamingResponse。
    错误码：5005/5003/6001。
    """
    # 1. 查 attempt → 5005（§7.4 step 1）
    attempt = await repo.get_attempt_by_id(db, attempt_id)
    if attempt is None:
        raise AppError(code=5005, message="答题尝试不存在", http_status=404)
    # 2. 所有权 → 5003（§7.4 step 2）
    if attempt.user_id != current_user.id:
        raise AppError(code=5003, message="无权操作该答题尝试", http_status=403)
    # 3. 查 uploaded 录音 → 6001（§7.4 step 3）
    recording = await repo.get_recording_for_download(db, attempt.id)
    if recording is None:
        raise AppError(code=6001, message="录音不存在", http_status=404)
    # 4. 读存储文件 → bytes（§7.4 step 4）
    try:
        file_bytes = storage.read(recording.storage_path)
    except OSError as exc:
        raise AppError(
            code=6001,
            message="录音文件读取失败",
            http_status=404,
        ) from exc

    return recording, file_bytes


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def _parse_path_id(raw: str, *, field: str) -> int:
    """Path id 字符串转 int，非合法数字 → 1001/422（practice.md §4.3 等）。"""
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": field, "message": f"{field} must be a positive integer"}],
        ) from exc
