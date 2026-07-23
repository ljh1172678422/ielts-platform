"""seed roles and Other topic

Revision ID: 017
Revises: 016
Create Date: 2026-07-23

对齐 database-design.md §9.1 / §9.2 / development-plan 任务 2.6（迁移部分）。
种子数据（硬编码，幂等）：
  - roles: 'user' / 'admin'
  - speaking_topics: 'Other'（兜底主题，sort_order=999，系统保留 ADR-024）
管理员账号通过 scripts/seed_admin.py 从环境变量创建（不硬编码，见 §9.3）。
downgrade 仅删种子，不删业务数据（§8.4）。
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "017"
down_revision: str | Sequence[str] | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # §9.1 角色种子（幂等：ON CONFLICT DO NOTHING）
    op.execute(
        """
        INSERT INTO roles (name, description) VALUES
            ('user',  '普通用户'),
            ('admin', '管理员')
        ON CONFLICT (name) DO NOTHING;
        """
    )
    # §9.2 Other 兜底主题（系统保留，sort_order=999 排末尾）
    op.execute(
        """
        INSERT INTO speaking_topics (name, description, sort_order) VALUES
            ('Other', '无明确分类的题目兜底主题', 999)
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    # §8.4 种子迁移 downgrade 只删种子，不删业务数据
    op.execute("DELETE FROM speaking_topics WHERE name = 'Other';")
    op.execute("DELETE FROM roles WHERE name IN ('user', 'admin');")
