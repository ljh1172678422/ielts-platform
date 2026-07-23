"""create users table

Revision ID: 002
Revises: 001
Create Date: 2026-07-23

对齐 database-design.md §3.1.2 / §8.1 拓扑序 02 / §4.1 索引。
软删除表：deleted_at。email 唯一约束（§7.2 软删除时应用层改名释放）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("email_verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_users_roles", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
    )
    # §4.1 索引（ix_users_email 由 uq_users_email 唯一约束隐含，跳过）
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index(
        "ix_users_status_deleted",
        "users",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_status_deleted", table_name="users")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_table("users")
