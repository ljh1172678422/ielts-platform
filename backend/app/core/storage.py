"""音频文件存储抽象（system-architecture §7）。

- 开发环境：本地 FS（/storage/recordings/<yyyy>/<mm>/<uuid>.<ext>）
- 生产环境：MinIO（S3 兼容，MVP 预留，未实现）

存储路径用 UUID，不暴露原文件名（practice.md §9.3）。
storage_path 存相对路径（local）或 object key（s3），业务无感。
"""
from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings

# mime_type → 扩展名映射（practice.md §6.1 白名单）
_MIME_TO_EXT: dict[str, str] = {
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}

# 允许的 mime_type 白名单（practice.md §6.1）
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(_MIME_TO_EXT.keys())

# 最大文件大小 50MB（practice.md §6.1）
MAX_FILE_SIZE: int = 50 * 1024 * 1024


class AudioStorage(ABC):
    """音频存储抽象接口（system-architecture §7.3）。"""

    @abstractmethod
    def save(self, data: bytes, *, mime_type: str) -> str:
        """保存音频文件，返回 storage_path（相对路径/object key）。"""

    @abstractmethod
    def read(self, storage_path: str) -> bytes:
        """读取音频文件全部内容（MVP 同步全量读；大文件未来改流式）。"""

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        """删除音频文件（事务回滚时清理临时文件）。"""

    @abstractmethod
    def exists(self, storage_path: str) -> bool:
        """检查文件是否存在。"""


class LocalStorageBackend(AudioStorage):
    """本地文件系统存储后端（system-architecture §7.1）。

    路径格式：{root}/recordings/<yyyy>/<mm>/<uuid>.<ext>
    storage_path 存相对路径：recordings/<yyyy>/<mm>/<uuid>.<ext>
    """

    def __init__(self, root: str | None = None) -> None:
        self._root = Path(root) if root else Path(get_settings().storage_local_path)

    def save(self, data: bytes, *, mime_type: str) -> str:
        ext = _MIME_TO_EXT.get(mime_type)
        if ext is None:
            raise ValueError(f"unsupported mime_type: {mime_type}")

        now = datetime.now(UTC)
        rel_dir = Path("recordings") / f"{now.year:04d}" / f"{now.month:02d}"
        abs_dir = self._root / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.{ext}"
        rel_path = rel_dir / filename
        abs_path = self._root / rel_path

        abs_path.write_bytes(data)
        return str(rel_path).replace(os.sep, "/")

    def read(self, storage_path: str) -> bytes:
        abs_path = self._root / storage_path
        return abs_path.read_bytes()

    def delete(self, storage_path: str) -> None:
        abs_path = self._root / storage_path
        if abs_path.exists():
            abs_path.unlink()

    def exists(self, storage_path: str) -> bool:
        return (self._root / storage_path).exists()

    def abs_path(self, storage_path: str) -> Path:
        """返回绝对路径（StreamingResponse 用，practice.md §7.4）。"""
        return self._root / storage_path


class S3StorageBackend(AudioStorage):
    """MinIO/S3 存储后端（system-architecture §7.2，MVP 未实现）。

    生产环境通过预签名 URL 上传/下载（未来优化）。
    """

    def save(self, data: bytes, *, mime_type: str) -> str:
        raise NotImplementedError("S3 storage not implemented in MVP")

    def read(self, storage_path: str) -> bytes:
        raise NotImplementedError("S3 storage not implemented in MVP")

    def delete(self, storage_path: str) -> None:
        raise NotImplementedError("S3 storage not implemented in MVP")

    def exists(self, storage_path: str) -> bool:
        raise NotImplementedError("S3 storage not implemented in MVP")


def get_storage() -> AudioStorage:
    """按配置创建存储后端（system-architecture §7.3，配置切换，业务无感）。"""
    settings = get_settings()
    if settings.storage_type == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()


def mime_to_ext(mime_type: str) -> str | None:
    """mime_type → 扩展名（白名单外返回 None）。"""
    return _MIME_TO_EXT.get(mime_type)


def cleanup_storage_on_failure(storage: AudioStorage, storage_path: str | None) -> None:
    """事务回滚时清理已写文件（practice.md §6.4 事务边界说明）。"""
    if storage_path is None:
        return
    try:
        storage.delete(storage_path)
    except OSError:
        pass


__all__ = [
    "ALLOWED_MIME_TYPES",
    "MAX_FILE_SIZE",
    "AudioStorage",
    "LocalStorageBackend",
    "S3StorageBackend",
    "cleanup_storage_on_failure",
    "get_storage",
    "mime_to_ext",
]
