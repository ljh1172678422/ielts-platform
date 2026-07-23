"""create practice_session_questions table

Revision ID: 011
Revises: 010
Create Date: 2026-07-23

对齐 database-design.md §3.3.2 / §8.1 拓扑序 11 / §4.3 索引。
question_snapshot JSONB：题目被修改/禁用后历史会话仍可还原作答时内容。
必含字段（应用层拷贝）：part/title/content/cue_card/topic_name/difficulty。
uq_session_questions_order (session_id, sort_order) 保证会话内顺序唯一。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | Sequence[str] | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "practice_session_questions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("question_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sort_order", name="uq_session_questions_order"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["practice_sessions.id"],
            name="fk_sq_sessions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["speaking_questions.id"],
            name="fk_sq_questions",
            ondelete="RESTRICT",
        ),
    )
    # §4.3 索引（ix_sq_session_id 由 uq_session_questions_order 复合唯一约束前缀隐含，跳过）
    op.create_index("ix_sq_question_id", "practice_session_questions", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_sq_question_id", table_name="practice_session_questions")
    op.drop_table("practice_session_questions")
