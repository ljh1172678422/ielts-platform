"""create practice_attempts table

Revision ID: 012
Revises: 011
Create Date: 2026-07-23

对齐 database-design.md §3.3.3 / §8.1 拓扑序 12 / §4.3 索引。
同一 session_question 可多 attempt（支持重录），attempt_number 从 1 递增。
uq_attempts_session_question_num (session_question_id, attempt_number) 保证编号不重复。
应用层新建 attempt 取 MAX(attempt_number)+1。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | Sequence[str] | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("session_question_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "session_question_id", "attempt_number", name="uq_attempts_session_question_num"
        ),
        sa.ForeignKeyConstraint(
            ["session_question_id"],
            ["practice_session_questions.id"],
            name="fk_attempts_sq",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_attempts_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'recording', 'submitted', 'skipped', 'failed')",
            name="ck_attempts_status",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_attempts_duration",
        ),
    )
    # §4.3 索引
    op.create_index(
        "ix_attempts_sq_id", "practice_attempts", ["session_question_id"]
    )
    op.create_index("ix_attempts_user_id", "practice_attempts", ["user_id"])
    op.create_index("ix_attempts_status", "practice_attempts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_attempts_status", table_name="practice_attempts")
    op.drop_index("ix_attempts_user_id", table_name="practice_attempts")
    op.drop_index("ix_attempts_sq_id", table_name="practice_attempts")
    op.drop_table("practice_attempts")
