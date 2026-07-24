"""Practice 模块路由（practice.md §1.2）。

所有 /practice 需 Bearer token（practice.md §1.2 全部接口标 Bearer）。
Path 参数 id 为字符串（ADR-025），路由层转 int；非合法数字 → 1001/422。

Phase 7 覆盖：会话创建/获取/完成 + attempt 创建/更新（practice.md §2-§5/§8）。
Phase 8 覆盖：录音上传/下载（practice.md §6/§7）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import AppError, success
from app.core.storage import ALLOWED_MIME_TYPES, MAX_FILE_SIZE, get_storage
from app.models.user import User
from app.modules.practice import service as practice_service
from app.modules.practice.schemas import (
    CreateAttemptRequest,
    CreateSessionRequest,
    UpdateAttemptRequest,
)

router = APIRouter(prefix="/practice", tags=["practice"])


def _parse_path_id(raw: str, *, field: str) -> int:
    """Path id 字符串转 int，非合法数字 → 1001/422（practice.md §3.3/§8.3 等）。"""
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": field, "message": f"{field} must be a positive integer"}],
        ) from exc


@router.post("/sessions")
async def create_session(
    payload: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """创建练习会话（practice.md §2）。"""
    data = await practice_service.create_session(
        db,
        current_user=current_user,
        mode=payload.mode,
        part=payload.part,
        topic_id=payload.topic_id,
        question_count=payload.question_count,
    )
    return success(data)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取会话详情（practice.md §3，含题目快照与 attempts）。"""
    sid = _parse_path_id(session_id, field="session_id")
    data = await practice_service.get_session(db, sid, current_user=current_user)
    return success(data)


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """完成会话（practice.md §8，ADR-015 跨表约束校验）。"""
    sid = _parse_path_id(session_id, field="session_id")
    data = await practice_service.complete_session(db, sid, current_user=current_user)
    return success(data)


@router.post("/attempts")
async def create_attempt(
    payload: CreateAttemptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """创建答题尝试（practice.md §4，首次创建激活 session）。"""
    data = await practice_service.create_attempt(
        db,
        current_user=current_user,
        session_question_id=payload.session_question_id,
    )
    return success(data)


@router.patch("/attempts/{attempt_id}")
async def update_attempt(
    attempt_id: str,
    payload: UpdateAttemptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """更新答题状态（practice.md §5，submitted 不可前端直设）。"""
    aid = _parse_path_id(attempt_id, field="attempt_id")
    data = await practice_service.update_attempt(
        db,
        aid,
        current_user=current_user,
        target_status=payload.status,
    )
    return success(data)


@router.post("/attempts/{attempt_id}/recording")
async def upload_recording(
    attempt_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """上传录音（practice.md §6，multipart/form-data，ADR-015 事务）。

    - file 字段缺失 → 1001/422（FastAPI File(...) 自动）
    - mime_type 白名单 → 6003；file_size > 50MB → 6004
    - 事务内 recording.uploaded → attempt.submitted → study_records 同步
    """
    aid = _parse_path_id(attempt_id, field="attempt_id")

    # 读文件内容 + 基本校验（practice.md §6.4 step 4）
    file_data = await file.read()
    mime_type = file.content_type or ""

    # FastAPI UploadFile 无直接 size，读完后 len 判断（50MB 限制）
    file_size = len(file_data)
    if file_size == 0:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "file", "message": "文件为空"}],
        )
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

    storage = get_storage()
    data = await practice_service.upload_recording(
        db,
        aid,
        current_user=current_user,
        file_data=file_data,
        mime_type=mime_type,
        file_size=file_size,
        storage=storage,
    )
    return success(data)


@router.get("/attempts/{attempt_id}/recording")
async def download_recording(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """下载录音（practice.md §7，直接返回音频流，非统一响应结构）。

    - 成功：StreamingResponse，Content-Type = recording.mime_type
    - 错误：仍走统一响应结构（5005/5003/6001）
    """
    aid = _parse_path_id(attempt_id, field="attempt_id")
    storage = get_storage()
    recording, file_bytes = await practice_service.download_recording(
        db,
        aid,
        current_user=current_user,
        storage=storage,
    )

    from io import BytesIO  # noqa: PLC0415

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=recording.mime_type,
        headers={
            "Content-Disposition": "inline",
            "Content-Length": str(len(file_bytes)),
        },
    )

