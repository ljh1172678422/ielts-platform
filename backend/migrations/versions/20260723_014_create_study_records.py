"""create study_records table

Revision ID: 014
Revises: 013
Create Date: 2026-07-23

对齐 database-design.md §3.4.1 / §8.1 拓扑序 14 / §4.4 索引。
ADR-008：每日聚合表，可重算覆盖，非事实来源。
ADR-016：duration_seconds = 当日 uploaded 录音时长和（非 session 时长）。
ADR-018：record_date 按 user_profiles.timezone 切日（非 UTC）。
ADR-022：MVP 同步更新，架构预留异步切换。
uq_study_records_user_date (user_id, record_date) 保证每用户每日一行。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | Sequence[str] | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("practice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recording_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("user_id", "record_date", name="uq_study_records_user_date"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_study_records_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "practice_count >= 0 AND question_count >= 0 "
            "AND attempt_count >= 0 AND duration_seconds >= 0 "
            "AND recording_count >= 0",
            name="ck_study_counts",
        ),
    )
    # §4.4 索引（ix_study_records_user_date 由 uq_study_records_user_date 唯一约束隐含，跳过）


def downgrade() -> None:
    op.drop_table("study_records")
