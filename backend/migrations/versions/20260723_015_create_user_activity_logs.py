"""create user_activity_logs table

Revision ID: 015
Revises: 014
Create Date: 2026-07-23

对齐 database-design.md §3.4.2 / §8.1 拓扑序 15 / §4.4 索引。
ADR-023：行为日志（非审计），在线保留 180 天，超期归档/删除（阶段 11/12）。
仅记录关键行为，不记录 UI 级交互噪音。
action 合法值由应用层校验（非 DB CHECK，便于扩展）。
日志表只有 created_at，无 updated_at（无需触发器）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: str | Sequence[str] | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_activity_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_logs_users", ondelete="RESTRICT"
        ),
    )
    # §4.4 索引（含 DESC 排序用 sa.text 包装）
    op.create_index(
        "ix_logs_user_created",
        "user_activity_logs",
        [sa.text("user_id"), sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_logs_action_created",
        "user_activity_logs",
        [sa.text("action"), sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_logs_action_created", table_name="user_activity_logs")
    op.drop_index("ix_logs_user_created", table_name="user_activity_logs")
    op.drop_table("user_activity_logs")
