"""领域模块包 (system-architecture §3.2)。

按域组织：auth / users / admin / questions / practice / learning / home。
每个模块导出 router，由 app.main 统一挂载到 /api/v1 前缀。
"""
from app.modules.admin import admin_router
from app.modules.auth import router as auth_router
from app.modules.home import home_router
from app.modules.learning import learning_router
from app.modules.practice import practice_router
from app.modules.questions import questions_router
from app.modules.users import router as users_router

__all__ = [
    "admin_router",
    "auth_router",
    "home_router",
    "learning_router",
    "practice_router",
    "questions_router",
    "users_router",
]
