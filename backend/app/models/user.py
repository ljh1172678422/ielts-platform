"""SQLAlchemy 2.x ORM 模型 — 用户域。

对齐 database-design.md v0.4 §3.1：
- roles / users / user_profiles / user_goals
- 主键 BIGINT GENERATED ALWAYS AS IDENTITY（ADR-013）
- 枚举 VARCHAR + CHECK（ADR：不用 PG ENUM）
- 软删除：users / user_goals 用 deleted_at
- snake_case 列名（ADR-026）

仅声明当前阶段（Phase 3-4）需要用到的表；其余域表在各自阶段添加。
UNIQUE 约束由 Alembic 迁移建表时显式声明（迁移是 DDL 真源），
模型层通过 mapped_column(unique=...) 仅用于 ORM 元数据提示，不重复建约束。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
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


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("name IN ('user', 'admin')", name="ck_roles_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled')", name="ck_users_status"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    profile: Mapped[UserProfile] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    role: Mapped[Role] = relationship(lazy="joined")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    nickname: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Shanghai")
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    user: Mapped[User] = relationship(back_populates="profile")


class UserGoal(Base):
    __tablename__ = "user_goals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'achieved', 'archived')",
            name="ck_user_goals_status",
        ),
        CheckConstraint(
            "target_score IS NULL OR (target_score >= 0 AND target_score <= 9)",
            name="ck_user_goals_score",
        ),
        CheckConstraint(
            "daily_goal_minutes IS NULL OR daily_goal_minutes >= 0",
            name="ck_user_goals_daily",
        ),
        CheckConstraint(
            "weekly_goal_minutes IS NULL OR weekly_goal_minutes >= 0",
            name="ck_user_goals_weekly",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_score: Mapped[float | None] = mapped_column(Numeric(3, 1))
    current_level: Mapped[str | None] = mapped_column(String(20))
    exam_date: Mapped[date | None] = mapped_column(Date)
    daily_goal_minutes: Mapped[int | None]
    weekly_goal_minutes: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()
