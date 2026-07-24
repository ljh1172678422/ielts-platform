"""SQLAlchemy 2.x ORM 模型 — 用户行为域（部分，当前阶段需要）。

对齐 database-design.md v0.4 §3.4：
- user_activity_logs: 原始行为日志（注册/登录/练习/录音/收藏/目标 等关键行为）
- study_records: 每日统计聚合（可重算，ADR-008）

无 updated_at（日志不可改）、无软删除（activity_logs）。
metadata JSONB、ip_address INET。
action 合法值由应用层校验（非 DB CHECK，便于扩展）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSON
    )
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )


class StudyRecord(Base):
    """每日学习统计聚合（database-design §3.4.1，ADR-008 可重算）。

    非事实来源，由事实表（sessions/attempts/recordings）聚合写入。
    MVP 同步更新（ADR-022）：录音上传/会话完成事务内 upsert。

    口径（PROJECT_SPEC §4.5.4）：
    - record_date：按 user_profiles.timezone 切日（ADR-018）
    - duration_seconds：当日 uploaded 录音时长总和（ADR-016，非 session 时长）
    """

    __tablename__ = "study_records"
    __table_args__ = (
        UniqueConstraint("user_id", "record_date", name="uq_study_records_user_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    practice_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    question_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    recording_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

