"""ORM 模型包 — 统一导出，确保 Alembic env.py 与应用层导入路径一致。

按域分模块组织（system-architecture §3.3）：
- user.py: roles / users / user_profiles / user_goals
- activity.py: user_activity_logs / study_records
- favorite.py: favorites（Phase 6）
- practice.py: practice_sessions / practice_session_questions / practice_attempts / recordings
- question.py: speaking_topics / tags / speaking_questions / question_tags
"""
from app.models.activity import StudyRecord, UserActivityLog
from app.models.favorite import Favorite
from app.models.practice import (
    PracticeAttempt,
    PracticeSession,
    PracticeSessionQuestion,
    Recording,
)
from app.models.user import Role, User, UserGoal, UserProfile

__all__ = [
    "Favorite",
    "PracticeAttempt",
    "PracticeSession",
    "PracticeSessionQuestion",
    "Recording",
    "Role",
    "StudyRecord",
    "User",
    "UserGoal",
    "UserProfile",
    "UserActivityLog",
]
