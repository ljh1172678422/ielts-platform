"""ORM 模型包 — 统一导出，确保 Alembic env.py 与应用层导入路径一致。

按域分模块组织（system-architecture §3.3）：
- user.py: roles / users / user_profiles / user_goals
- activity.py: user_activity_logs
- favorite.py: favorites（Phase 6）
- practice.py: practice_session_questions（Phase 6 最小，Phase 7 扩展）
- question.py: speaking_topics / tags / speaking_questions / question_tags
"""
from app.models.activity import UserActivityLog
from app.models.favorite import Favorite
from app.models.practice import PracticeSessionQuestion
from app.models.user import Role, User, UserGoal, UserProfile

__all__ = [
    "Favorite",
    "PracticeSessionQuestion",
    "Role",
    "User",
    "UserGoal",
    "UserProfile",
    "UserActivityLog",
]
