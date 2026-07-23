"""Questions 模块（用户端）Pydantic schemas（对齐 questions.md §7 DTO 速查）。

id 序列化为 str（ADR-025），全部 snake_case（ADR-026）。
用户端不暴露 created_by / status / updated_at（questions.md §6.3）。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TopicRef(BaseModel):
    id: str
    name: str


class TagRef(BaseModel):
    id: str
    name: str


class QuestionListItem(BaseModel):
    """题库列表项（questions.md §2.2，不含 content/cue_card/tags/source_*）。"""

    id: str
    part: int
    title: str
    topic: TopicRef
    difficulty: int | None
    is_favorited: bool
    practice_count: int
    created_at: datetime


class QuestionDetail(QuestionListItem):
    """题目详情（questions.md §3.2，在列表项基础上追加完整字段）。"""

    content: str
    cue_card: str | None
    tags: list[TagRef]
    source_type: str
    source_name: str


class FavoriteResponse(BaseModel):
    """收藏/取消收藏响应（questions.md §4.2/§5.2）。"""

    question_id: str
    is_favorited: bool
