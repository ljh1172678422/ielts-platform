"""用户模块路由 (users.md §2-§7)。

Phase 3.7 仅挂载前缀与占位，Phase 4.4-4.6 实现 me/password/goals。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])
