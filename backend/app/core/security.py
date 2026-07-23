"""Security primitives: JWT HS256 + bcrypt (auth.md §5, common.md §6).

对齐 auth.md §5：
- JWT 载荷 {sub, role, email, iat, exp}，sub 为 user_id 字符串化（ADR-025）。
- 算法 HS256，密钥 JWT_SECRET，有效期 24h（86400s），无 refresh_token（ADR-027）。
对齐 common.md §6.1 / auth.md §6.1：
- bcrypt cost ≥ 12。

不使用 passlib（passlib 1.7.4 与 bcrypt 4.x 存在已知兼容 bug：
bcrypt.__about__ 已移除 + 72 字节 wrap 检测失败）。直接调用 bcrypt
原生 API，行为等价且依赖更少（bcrypt 已在 pyproject 依赖）。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AppError

# bcrypt cost ≥ 12（auth.md §6.1）
_BCRYPT_COST = 12
# bcrypt 72 字节限制（auth.md §6.1），超长先截断再哈希
_BCRYPT_MAX_BYTES = 72

_settings = get_settings()


def hash_password(plain: str) -> str:
    """bcrypt 哈希明文密码，cost=12。返回 UTF-8 字符串哈希。"""
    pwd_bytes = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(_BCRYPT_COST)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    pwd_bytes = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    *, user_id: int, role: str, email: str
) -> tuple[str, int]:
    """签发 JWT。

    返回 (token, expires_in_seconds)。sub 为字符串化 user_id（ADR-025）。
    """
    now = datetime.now(UTC)
    expires_in = _settings.jwt_expires_seconds
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(
        payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm
    )
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """解码并校验 JWT。

    成功返回 payload dict（含 sub/role/email/iat/exp）。
    失败抛 AppError(2002, 401) —— token 无效或已过期（common.md §3.2）。
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            _settings.jwt_secret,
            algorithms=[_settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AppError(
            code=2002,
            message="token 无效或已过期",
            http_status=401,
            details=[{"field": "token", "message": str(exc)}],
        ) from exc

    if "sub" not in payload or "role" not in payload:
        raise AppError(
            code=2002,
            message="token 无效或已过期",
            http_status=401,
            details=[{"field": "token", "message": "missing sub/role claim"}],
        )
    return payload
