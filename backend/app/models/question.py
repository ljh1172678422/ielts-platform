"""SQLAlchemy 2.x ORM 模型 — 题库域。

对齐 database-design.md v0.4 §3.2 / 迁移 005-008（DDL 真源）：
- speaking_topics / tags / speaking_questions / question_tags
- 主键 BIGINT GENERATED ALWAYS AS IDENTITY（ADR-013）
- 枚举 VARCHAR + CHECK（ADR：不用 PG ENUM）
- 软删除：topics / tags 用 deleted_at；questions 用 status='disabled'（ADR-010，无 deleted_at）
- snake_case 列名（ADR-026）

注：DB schema 无 slug 列（迁移 005/006 未建），admin.md §4/§5 响应中的 slug
由 name 派生（MVP：slug = name），不存 DB，避免修改已锁定 schema。
is_system 同理派生（name == 'Other' → True）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _ts() -> Mapped[datetime]:
    """TIMESTAMPTZ NOT NULL DEFAULT NOW() 的通用列定义。"""
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )


class SpeakingTopic(Base):
    """主题。Other 为系统保留（ADR-024 / PROJECT_SPEC §12.3）。"""

    __tablename__ = "speaking_topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    questions: Mapped[list[SpeakingQuestion]] = relationship(
        back_populates="topic", lazy="selectin"
    )


class Tag(Base):
    """标签。无系统保留。"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class SpeakingQuestion(Base):
    """题目。ADR-010：无 deleted_at，status='disabled' 软停用保历史引用。"""

    __tablename__ = "speaking_questions"
    __table_args__ = (
        CheckConstraint("part IN (1, 2, 3)", name="ck_questions_part"),
        CheckConstraint(
            "status IN ('draft', 'published', 'disabled')", name="ck_questions_status"
        ),
        CheckConstraint(
            "source_type IN ('official', 'historical', 'mock', 'custom')",
            name="ck_questions_source",
        ),
        CheckConstraint(
            "difficulty IS NULL OR (difficulty >= 1 AND difficulty <= 5)",
            name="ck_questions_difficulty",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    topic_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("speaking_topics.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cue_card: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="custom", server_default="custom")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    topic: Mapped[SpeakingTopic] = relationship(back_populates="questions", lazy="joined")
    tags: Mapped[list[Tag]] = relationship(
        secondary="question_tags", lazy="selectin"
    )


class QuestionTag(Base):
    """题目-标签关联表（ADR-017：复合主键，无独立 id）。"""

    __tablename__ = "question_tags"

    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("speaking_questions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = _ts()
