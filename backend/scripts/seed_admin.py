"""Seed initial admin account.

对齐 database-design.md §9.3 / §9.4 / development-plan 任务 2.6（脚本部分）。
凭证来自环境变量（SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD / SEED_ADMIN_NICKNAME），
绝不写入代码库。幂等：已存在 active 管理员则跳过。

运行方式（在 backend/ 目录下）：
    uv run python -m scripts.seed_admin

依赖迁移 017 已执行（roles 表含 'admin' 角色）。
"""
from __future__ import annotations

import sys

from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings

# bcrypt cost ≥ 12（common.md §6 / auth.md §5）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

MIN_PASSWORD_LENGTH = 12


def _validate_password_strength(password: str, *, production: bool) -> None:
    """生产环境校验密码强度（§9.4）。开发环境跳过。"""
    if not production:
        return
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"[seed_admin] 生产环境密码长度必须 >= {MIN_PASSWORD_LENGTH}")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        sys.exit("[seed_admin] 生产环境密码必须同时包含字母与数字")


def main() -> None:
    settings = get_settings()
    _validate_password_strength(
        settings.seed_admin_password, production=settings.is_production
    )

    engine = create_engine(settings.database_sync_url)
    try:
        with Session(engine) as session:
            # 依赖迁移 017：roles 表含 'admin' 角色
            row = session.execute(text("SELECT id FROM roles WHERE name = 'admin'")).fetchone()
            if row is None:
                sys.exit("[seed_admin] roles 表缺少 'admin' 角色，请先执行 alembic upgrade head")
            admin_role_id = row[0]

            # 幂等：已存在 active 管理员则跳过
            existing = session.execute(
                text(
                    "SELECT id FROM users "
                    "WHERE email = :email AND role_id = :role_id "
                    "AND status = 'active' AND deleted_at IS NULL"
                ),
                {"email": settings.seed_admin_email, "role_id": admin_role_id},
            ).fetchone()
            if existing is not None:
                print(f"[seed_admin] 管理员已存在，跳过: {settings.seed_admin_email}")
                return

            password_hash = pwd_context.hash(settings.seed_admin_password)

            user_id = session.execute(
                text(
                    "INSERT INTO users "
                    "(email, password_hash, role_id, status, email_verified_at) "
                    "VALUES (:email, :hash, :role_id, 'active', NOW()) "
                    "RETURNING id"
                ),
                {
                    "email": settings.seed_admin_email,
                    "hash": password_hash,
                    "role_id": admin_role_id,
                },
            ).scalar_one()

            session.execute(
                text(
                    "INSERT INTO user_profiles (user_id, nickname) "
                    "VALUES (:user_id, :nickname)"
                ),
                {"user_id": user_id, "nickname": settings.seed_admin_nickname},
            )
            session.commit()
            # 不回显密码（§9.4）
            print(f"[seed_admin] 管理员已创建: {settings.seed_admin_email}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
