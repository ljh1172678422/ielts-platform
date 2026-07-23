"""认证模块 — 注册/登录/退出 (auth.md)。

分层（system-architecture §3）：
- router.py: FastAPI 路由 + Pydantic 入参校验 + 依赖注入
- service.py: 业务逻辑 + 事务边界 + 跨表约束校验
- repository.py: SQLAlchemy 查询封装
- schemas.py: 请求/响应 Pydantic 模型
"""
from app.modules.auth.router import router

__all__ = ["router"]
