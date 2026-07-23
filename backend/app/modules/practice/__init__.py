"""Practice 模块：练习会话与答题尝试状态机。

对齐 practice.md v0.1：会话创建/获取/完成 + attempt 创建/更新（Phase 7）。
录音上传/下载（§6/§7）在 Phase 8 接入。
"""
from app.modules.practice.router import router as practice_router

__all__ = ["practice_router"]
