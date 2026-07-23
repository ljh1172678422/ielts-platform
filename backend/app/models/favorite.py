"""SQLAlchemy 2.x ORM 模型 — 收藏（行为域）。

对齐 database-design.md v0.4 §3.2.5 / 迁移 009（DDL 真源）：
- favorites: 用户-题目收藏关系
- 无 status / deleted_at：存在即收藏，删除即取消（PROJECT_SPEC §4.4）
- uq_favorites_user_question 唯一约束支撑幂等 ON CONFLICT DO NOTHING
- ON DELETE CASCADE（关联表随主体消失）
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_favorites_user_question"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("speaking_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
