"""Unified exception & response envelope (common.md §2/§3).

对齐 common.md：
- 统一响应 {code, message, data, details?}
- 成功 code=0
- 错误时 data=null
- FastAPI 默认 422 改写为 common.md 格式
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ResponseEnvelope(BaseModel):
    """统一响应结构 (common.md §2.1)。"""

    code: int = 0
    message: str = "ok"
    data: Any = None
    details: Any = None


class AppError(Exception):
    """业务异常基类，携带 code/message/http_status/details。

    子类或实例化时指定 code（对齐 common.md §3.2 错误码段）。
    """

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details


def success(data: Any = None, message: str = "ok") -> dict[str, Any]:
    """成功响应助手。永远包含 data（即使为 null），不含 details（common.md §2.1）。"""
    return {"code": 0, "message": message, "data": data}


def _error_content(
    code: int, message: str, details: Any = None
) -> dict[str, Any]:
    """错误响应体：data 恒为 null，details 仅在非空时出现（common.md §2.2）。"""
    content: dict[str, Any] = {"code": code, "message": message, "data": None}
    if details is not None:
        content["details"] = details
    return content


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理器到 FastAPI app。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_content(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # common.md §3.2: 1001 参数校验失败 → 422
        return JSONResponse(
            status_code=422,
            content=_error_content(1001, "参数校验失败", exc.errors()),
        )
