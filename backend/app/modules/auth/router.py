"""认证模块路由 (auth.md §2/§3/§4)。

Phase 3.7 仅挂载前缀与占位，Phase 4.1-4.3 实现 register/login/logout。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
