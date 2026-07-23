"""create updated_at trigger function and per-table triggers

Revision ID: 016
Revises: 015
Create Date: 2026-07-23

对齐 database-design.md §8.3 / development-plan 任务 2.7。
PostgreSQL 不自动更新 updated_at，需建触发器函数 + 每表触发器。
仅对含 updated_at 的 11 张业务表建触发器（跳过 question_tags/favorites/
practice_session_questions/user_activity_logs，这 4 表只有 created_at）。
验收：UPDATE 后 updated_at 自动变化。
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "016"
down_revision: str | Sequence[str] | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 含 updated_at 的表（按建表顺序）
TABLES_WITH_UPDATED_AT = [
    "roles",
    "users",
    "user_profiles",
    "user_goals",
    "speaking_topics",
    "tags",
    "speaking_questions",
    "practice_sessions",
    "practice_attempts",
    "recordings",
    "study_records",
]


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
        )


def downgrade() -> None:
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
