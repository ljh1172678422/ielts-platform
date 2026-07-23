"""SQLAlchemy 2.x ORM 模型 — 用户行为域（部分，当前阶段需要）。

对齐 database-design.md v0.4 §3.4.2：
- user_activity_logs: 原始行为日志（注册/登录/练习/录音/收藏/目标 等关键行为）
- 无 updated_at（日志不可改）、无软删除
- metadata JSONB、ip_address INET
- action 合法值由应用层校验（非 DB CHECK，便于扩展）

仅声明 Phase 3-4 需要的表；favorites / study_records 在各自阶段添加。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String
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
