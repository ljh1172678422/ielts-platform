"""Unified exception & response envelope (common.md §2/§3).

对齐 common.md：
- 统一响应 {code, message, data, details?}
- 成功 code=0
- 错误时 data=null
- FastAPI 默认 422 改写为 common.md 格式
- HTTPException / 未捕获异常 兜底为统一信封（9001/9000）
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


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


# Starlette HTTPException 状态码 → common.md 错误码映射
_HTTP_STATUS_TO_CODE: dict[int, tuple[int, str]] = {
    400: (1002, "请求参数错误"),
    401: (2001, "未登录"),
    403: (2003, "无权限"),
    404: (1004, "资源不存在"),
    405: (1005, "方法不允许"),
    409: (1006, "资源冲突"),
    413: (1007, "请求体过大"),
    429: (9002, "请求过于频繁"),
}


def register_exception_handlers(app: FastAPI) -> None:
    """注册统一异常处理器到 FastAPI app。

    处理顺序（FastAPI 按异常类型匹配，子类优先）：
    1. AppError → 业务自定义 code/http_status
    2. RequestValidationError → 1001/422（Pydantic 校验失败）
    3. StarletteHTTPException → 状态码映射到 common.md 错误码
    4. Exception → 9000/500（兜底，记录日志）
    """

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

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code, msg = _HTTP_STATUS_TO_CODE.get(
            exc.status_code, (9001, f"HTTP {exc.status_code}")
        )
        # 优先用异常自带 detail 作为 message（若非默认占位）
        message = msg
        if exc.detail and exc.detail != f"{exc.status_code}: {msg}":
            message = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_content(code, message),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(
        req: Request, exc: Exception
    ) -> JSONResponse:
        # common.md §3.2: 9000 系统内部错误 → 500
        logger.exception(
            "Unhandled exception on %s %s", req.method, req.url.path
        )
        return JSONResponse(
            status_code=500,
            content=_error_content(9000, "系统内部错误"),
        )
