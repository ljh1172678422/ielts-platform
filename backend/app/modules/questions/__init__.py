"""Questions 模块（用户端）：题库浏览与收藏。

对齐 questions.md v0.1：列表(筛选+分页+排序) + 详情 + 收藏(POST/DELETE)。
仅用户端读 + 收藏操作；管理员 CRUD 在 admin 模块。
"""
from app.modules.questions.router import router as questions_router

__all__ = ["questions_router"]
