"""ORM 模型包 — 统一导出，确保 Alembic env.py 与应用层导入路径一致。

按域分模块组织（system-architecture §3.3）：
- user.py: roles / users / user_profiles / user_goals
- (后续阶段添加: question / practice / behavior)
"""
from app.models.user import Role, User, UserGoal, UserProfile

__all__ = ["Role", "User", "UserGoal", "UserProfile"]
