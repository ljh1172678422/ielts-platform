"""Application configuration via pydantic-settings.

对齐 system-architecture §8 与 common.md 安全约定。
环境变量从 .env 读取，缺省值仅供开发环境。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    app_name: str = "ielts-speaking"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ielts:ielts@localhost:5432/ielts_speaking"
    )
    database_sync_url: str = Field(
        default="postgresql+psycopg2://ielts:ielts@localhost:5432/ielts_speaking"
    )

    # JWT (auth.md §5)
    jwt_secret: str = "change-me-to-a-random-32-byte-secret"
    jwt_algorithm: str = "HS256"
    jwt_expires_seconds: int = 86400

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:5174"]
    )

    # Storage (system-architecture §7)
    storage_type: Literal["local", "s3"] = "local"
    storage_local_path: str = "./storage"

    # Admin seed (Phase 2 seed_admin script, database-design §9.3)
    # 用 .dev 域名：.local 是 ICANN 保留域名，会被 EmailStr 拒绝（pydantic email-validator）
    seed_admin_email: str = "admin@ielts.dev"
    seed_admin_password: str = "change-me"
    seed_admin_nickname: str = "Admin"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
