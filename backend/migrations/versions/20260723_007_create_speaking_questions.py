"""create speaking_questions table

Revision ID: 007
Revises: 006
Create Date: 2026-07-23

对齐 database-design.md §3.2.3 / §8.1 拓扑序 07 / §4.2 索引。
ADR-010：无 deleted_at，用 status='disabled' 软停用（保历史会话引用完整性）。
ADR-019：topic_id NOT NULL，无主题归入种子 Other。
ADR-011：source_type + source_name 强制（版权合规）。
created_by → users ON DELETE SET NULL（题目不因创建者删除而消失）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | Sequence[str] | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speaking_questions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("part", sa.SmallInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cue_card", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="custom"),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
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
            ["topic_id"], ["speaking_topics.id"], name="fk_questions_topics", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_questions_users", ondelete="SET NULL"
        ),
        sa.CheckConstraint("part IN (1, 2, 3)", name="ck_questions_part"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'disabled')", name="ck_questions_status"
        ),
        sa.CheckConstraint(
            "source_type IN ('official', 'historical', 'mock', 'custom')",
            name="ck_questions_source",
        ),
        sa.CheckConstraint(
            "difficulty IS NULL OR (difficulty >= 1 AND difficulty <= 5)",
            name="ck_questions_difficulty",
        ),
    )
    # §4.2 索引
    op.create_index("ix_questions_topic_id", "speaking_questions", ["topic_id"])
    op.create_index("ix_questions_status_part", "speaking_questions", ["status", "part"])
    op.create_index("ix_questions_source_type", "speaking_questions", ["source_type"])
    op.create_index("ix_questions_created_by", "speaking_questions", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_questions_created_by", table_name="speaking_questions")
    op.drop_index("ix_questions_source_type", table_name="speaking_questions")
    op.drop_index("ix_questions_status_part", table_name="speaking_questions")
    op.drop_index("ix_questions_topic_id", table_name="speaking_questions")
    op.drop_table("speaking_questions")
