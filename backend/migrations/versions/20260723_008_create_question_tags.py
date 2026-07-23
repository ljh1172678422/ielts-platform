"""create question_tags table

Revision ID: 008
Revises: 007
Create Date: 2026-07-23

对齐 database-design.md §3.2.4 / §8.1 拓扑序 08 / §4.2 索引。
ADR-017：纯关联表，复合主键 (question_id, tag_id) 不设独立 id。
ON DELETE CASCADE（关联表随主体消失）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | Sequence[str] | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_tags",
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("question_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["speaking_questions.id"],
            name="fk_qt_questions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name="fk_qt_tags", ondelete="CASCADE"),
    )
    # §4.2 反向查询索引（复合主键前缀为 question_id，tag_id 反向需单独索引）
    op.create_index("ix_question_tags_tag_id", "question_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_question_tags_tag_id", table_name="question_tags")
    op.drop_table("question_tags")
