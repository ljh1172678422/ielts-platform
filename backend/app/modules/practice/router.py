"""Practice 模块路由（practice.md §1.2）。

所有 /practice 需 Bearer token（practice.md §1.2 全部接口标 Bearer）。
Path 参数 id 为字符串（ADR-025），路由层转 int；非合法数字 → 1001/422。

Phase 7 覆盖：会话创建/获取/完成 + attempt 创建/更新（practice.md §2-§5/§8）。
录音上传/下载（§6/§7）在 Phase 8 接入。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import AppError, success
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
