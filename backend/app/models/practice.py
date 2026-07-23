"""SQLAlchemy 2.x ORM 模型 — 练习域。

对齐 database-design.md v0.4 §3.3 / 迁移 010-013（DDL 真源）：
- practice_sessions / practice_session_questions / practice_attempts / recordings
- 核心事实链：Session → SessionQuestion → Attempt → Recording（ADR-006/007）
- 枚举 VARCHAR + CHECK（迁移层建约束，模型层仅映射）
- snake_case 列名（ADR-026）

Phase 6 建立了 PracticeSessionQuestion（questions 模块统计 practice_count 用）；
Phase 7 追加 PracticeSession / PracticeAttempt / Recording 完整模型。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PracticeSession(Base):
    """练习会话主表（practice.md §2，事实链根表）。

    无 deleted_at，用 status 软状态（created/in_progress/completed/abandoned/expired）。
    created → in_progress 由首次创建 attempt 触发（practice.md §4.4）。
    """

    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    part_filter: Mapped[int | None] = mapped_column(SmallInteger)
    topic_filter: Mapped[int | None] = mapped_column(BigInteger)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created", server_default="created"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )


class PracticeSessionQuestion(Base):
    """练习会话-题目关联表（question_snapshot 保留历史作答内容）。

    questions 模块用本表 COUNT(question_id) 统计 practice_count
    （questions.md §2.4/§3.4）；practice 模块读取 question_snapshot 还原作答时内容。
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


class PracticeAttempt(Base):
    """答题尝试（practice.md §4，ADR-006）。

    同一 session_question 可多 attempt（支持重录），attempt_number 从 1 递增。
    submitted 只能由录音上传事务设置（ADR-015），不可通过 PATCH 直设。
    """

    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint(
            "session_question_id",
            "attempt_number",
            name="uq_attempts_session_question_num",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("practice_session_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )


class Recording(Base):
    """录音元数据（practice.md §6/§7，ADR-007 绑定 attempt）。

    MVP attempt_id 唯一（1:1），未来放开唯一约束即支持一题多录音。
    storage_path 用 UUID，不暴露原文件名（practice.md §9.3）。
    软删除：deleted_at + status='deleted'。
    """

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("practice_attempts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    storage_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="local", server_default="local"
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="audio/webm", server_default="audio/webm"
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploading", server_default="uploading"
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
