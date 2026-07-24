"""Home 模块包（system-architecture §5.6）。

对齐 home.md §1.2：单接口 GET /home/overview，聚合首页数据 +
ADR-028 确定性推荐 5 级短路。读接口仅 Bearer。
"""
from app.modules.home.router import router as home_router

__all__ = ["home_router"]
