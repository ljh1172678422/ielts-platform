"""create user_goals table

Revision ID: 004
Revises: 003
Create Date: 2026-07-23

对齐 database-design.md §3.1.4 / §8.1 拓扑序 04 / §4.1 索引。
软删除表：deleted_at。4 个 CHECK 约束。
ADR-014：active 目标用部分唯一索引 uq_user_goals_active（同时仅一个 active）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_goals",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("target_score", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("current_level", sa.String(length=20), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("daily_goal_minutes", sa.Integer(), nullable=True),
        sa.Column("weekly_goal_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_goals_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("status IN ('active', 'achieved', 'archived')", name="ck_user_goals_status"),
        sa.CheckConstraint(
            "target_score IS NULL OR (target_score >= 0 AND target_score <= 9)",
            name="ck_user_goals_score",
        ),
        sa.CheckConstraint(
            "daily_goal_minutes IS NULL OR daily_goal_minutes >= 0",
            name="ck_user_goals_daily",
        ),
        sa.CheckConstraint(
            "weekly_goal_minutes IS NULL OR weekly_goal_minutes >= 0",
            name="ck_user_goals_weekly",
        ),
    )
    # §4.1 索引
    op.create_index("ix_user_goals_user_id", "user_goals", ["user_id"])
    # ADR-014 部分唯一索引：同一用户同时仅一个 active 目标
    op.create_index(
        "uq_user_goals_active",
        "user_goals",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_goals_active", table_name="user_goals")
    op.drop_index("ix_user_goals_user_id", table_name="user_goals")
    op.drop_table("user_goals")
