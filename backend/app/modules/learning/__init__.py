"""Learning 模块包（system-architecture §3.2）。

对齐 learning.md §1.2：7 接口路由（overview / daily / weekly / monthly /
topics / parts / recompute）。读接口仅 Bearer + 当前用户；
recompute 需 admin（learning.md §8）。
"""
from app.modules.learning.router import router as learning_router

__all__ = ["learning_router"]
