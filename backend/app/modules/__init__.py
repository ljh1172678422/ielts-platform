"""领域模块包 (system-architecture §3.2)。

按域组织：auth / users / admin / (后续 questions / practice / learning / home)。
每个模块导出 router，由 app.main 统一挂载到 /api/v1 前缀。
"""
from app.modules.admin import admin_router
from app.modules.auth import router as auth_router
from app.modules.users import router as users_router

__all__ = ["admin_router", "auth_router", "users_router"]
