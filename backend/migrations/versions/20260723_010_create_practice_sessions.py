"""create practice_sessions table

Revision ID: 010
Revises: 009
Create Date: 2026-07-23

对齐 database-design.md §3.3.1 / §8.1 拓扑序 10 / §4.3 索引。
练习域核心事实链根表。无 deleted_at，用 status 软状态。
4 个 CHECK 约束（mode/status/part_filter/count）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | Sequence[str] | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("part_filter", sa.SmallInteger(), nullable=True),
        sa.Column("topic_filter", sa.BigInteger(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="created"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
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
            ["user_id"], ["users.id"], name="fk_sessions_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("mode IN ('random', 'topic', 'part')", name="ck_sessions_mode"),
        sa.CheckConstraint(
            "status IN ('created', 'in_progress', 'completed', 'abandoned', 'expired')",
            name="ck_sessions_status",
        ),
        sa.CheckConstraint(
            "part_filter IS NULL OR part_filter IN (1, 2, 3)",
            name="ck_sessions_part_filter",
        ),
        sa.CheckConstraint(
            "question_count > 0 AND question_count <= 50", name="ck_sessions_count"
        ),
    )
    # §4.3 索引（含 DESC 排序用 sa.text 包装）
    op.create_index(
        "ix_sessions_user_status",
        "practice_sessions",
        [sa.text("user_id"), sa.text("status"), sa.text("created_at DESC")],
    )
    op.create_index("ix_sessions_status", "practice_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sessions_status", table_name="practice_sessions")
    op.drop_index("ix_sessions_user_status", table_name="practice_sessions")
    op.drop_table("practice_sessions")
