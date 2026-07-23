"""SQLAlchemy 2.x ORM 模型 — 练习域（部分）。

对齐 database-design.md v0.4 §3.3 / 迁移 010-013（DDL 真源）。

Phase 6 仅声明 questions 模块统计 practice_count 所需的最小模型
（practice_session_questions 表，用于 LEFT JOIN 统计题目被练习次数）。
Phase 7 接入练习系统时在本文件追加 PracticeSession / PracticeAttempt / Recording
等完整模型，不修改本表定义。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PracticeSessionQuestion(Base):
    """练习会话-题目关联表（question_snapshot 保留历史作答内容）。

    questions 模块仅用本表 COUNT(question_id) 统计 practice_count
    （questions.md §2.4/§3.4），不读取 question_snapshot。
    """

    __tablename__ = "practice_session_questions"
    __table_args__ = (
        UniqueConstraint("session_id", "sort_order", name="uq_session_questions_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("speaking_questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    question_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
