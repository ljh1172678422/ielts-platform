"""Questions 模块（用户端）路由（questions.md §1.2）。

所有 /questions 需 Bearer token（questions.md §1.2 全部接口标 Bearer）。
Path 参数 id 为字符串（ADR-025），路由层转 int；非合法数字 → 1001/422。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import AppError, success
from app.models.user import User
from app.modules.questions import service as question_service

router = APIRouter(prefix="/questions", tags=["questions"])


def _parse_question_id(raw: str) -> int:
    """Path id 字符串转 int，非合法数字 → 1001/422（questions.md §3.3/§4.3/§5.3）。"""
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise AppError(
            code=1001,
            message="参数校验失败",
            http_status=422,
            details=[{"field": "id", "message": "id must be a positive integer"}],
        ) from exc


@router.get("")
async def list_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    part: int | None = Query(default=None, ge=1, le=3),
    topic_id: str | None = Query(default=None),
    tag_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=100),
    difficulty: int | None = Query(default=None, ge=1, le=5),
    sort: str = Query(default="newest", pattern="^(newest|popular)$"),
    is_favorited: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """题库列表（questions.md §2，分页+筛选+排序）。

    topic_id/tag_id 为字符串化 ID，转 int；非合法数字视为筛选无匹配（返回空列表，
    §2.3 不报错）。sort 非法值由 FastAPI pattern 校验 → 1001/422。
    """
    topic_id_int = _parse_optional_id(topic_id)
    tag_id_int = _parse_optional_id(tag_id)
    data = await question_service.list_questions(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        part=part,
        topic_id=topic_id_int,
        difficulty=difficulty,
        keyword=keyword,
        tag_id=tag_id_int,
        is_favorited=is_favorited,
        sort=sort,
    )
    return success(data)


@router.get("/{question_id}")
async def get_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """题目详情（questions.md §3，4001/4002 分级）。"""
    qid = _parse_question_id(question_id)
    data = await question_service.get_question_detail(db, qid, current_user=current_user)
    return success(data)


@router.post("/{question_id}/favorite")
async def favorite_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """收藏题目（questions.md §4，幂等）。"""
    qid = _parse_question_id(question_id)
    data = await question_service.favorite_question(db, qid, current_user=current_user)
    return success(data)


@router.delete("/{question_id}/favorite")
async def unfavorite_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """取消收藏（questions.md §5，幂等，不校验题目状态）。"""
    qid = _parse_question_id(question_id)
    data = await question_service.unfavorite_question(db, qid, current_user=current_user)
    return success(data)


def _parse_optional_id(raw: str | None) -> int | None:
    """可选字符串 ID 转 int；None → None，非合法数字 → None（筛选视为无匹配，§2.3）。

    列表筛选的 topic_id/tag_id 非法时不报错（返回空列表），与详情/收藏的 path id
    分级不同：path id 非法 → 1001/422，query 筛选 id 非法 → 空结果。
    """
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        # 非法 query id：用 -1 占位（不可能匹配任何真实 id → 空列表，§2.3）
        return -1
