"""create recordings table

Revision ID: 013
Revises: 012
Create Date: 2026-07-23

对齐 database-design.md §3.3.4 / §8.1 拓扑序 13 / §4.3 索引。
ADR-007：录音绑定 attempt。MVP attempt_id 唯一（1:1），未来放开唯一约束即支持一题多录音。
软删除：deleted_at + status='deleted'。
ADR-020：duration_seconds 后端读音频元数据计算（不信前端）。
ADR-021：mime_type MVP 不转码，存原始格式。
跨表状态约束（应用层 service 校验，见 §3.3.4 说明）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | Sequence[str] | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recordings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("storage_type", sa.String(length=20), nullable=False, server_default="local"),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(length=50), nullable=False, server_default="audio/webm"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="uploading"),
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
        sa.UniqueConstraint("attempt_id", name="uq_recordings_attempt"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["practice_attempts.id"],
            name="fk_recordings_attempts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_recordings_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "storage_type IN ('local', 's3')", name="ck_recordings_storage"
        ),
        sa.CheckConstraint(
            "status IN ('uploading', 'uploaded', 'failed', 'deleted')",
            name="ck_recordings_status",
        ),
        sa.CheckConstraint(
            "file_size IS NULL OR file_size >= 0", name="ck_recordings_size"
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_recordings_duration",
        ),
    )
    # §4.3 索引（ix_recordings_attempt_id 由 uq_recordings_attempt 唯一约束隐含，跳过）
    op.create_index("ix_recordings_user_id", "recordings", ["user_id"])
    op.create_index("ix_recordings_status", "recordings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_recordings_status", table_name="recordings")
    op.drop_index("ix_recordings_user_id", table_name="recordings")
    op.drop_table("recordings")
