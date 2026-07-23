"""create favorites table

Revision ID: 009
Revises: 008
Create Date: 2026-07-23

对齐 database-design.md §3.2.5 / §8.1 拓扑序 09 / §4.2 索引。
行为域表，但拓扑序位于题库域与练习域之间（依赖 users + speaking_questions）。
无 status / deleted_at：存在即收藏，删除即取消（PROJECT_SPEC §4.4）。
ON DELETE CASCADE（关联表随主体消失）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | Sequence[str] | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "question_id", name="uq_favorites_user_question"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_favorites_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["speaking_questions.id"],
            name="fk_favorites_questions",
            ondelete="CASCADE",
        ),
    )
    # §4.2 索引
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_question_id", "favorites", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_favorites_question_id", table_name="favorites")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_table("favorites")
