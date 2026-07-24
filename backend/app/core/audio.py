"""音频元数据读取（ADR-020：duration_seconds 后端读元数据计算，不信前端）。

使用 mutagen（纯 Python，支持 webm/mp4/mpeg/wav）。
不引入 FFmpeg（ADR-021：MVP 不转码）。

支持的 mime_type（practice.md §6.1 白名单）：
- audio/webm → mutagen.easywebm / WebM
- audio/mp4  → mutagen.mp4.MP4
- audio/mpeg → mutagen.mp3.MP3 / mutagen.easyid3
- audio/wav  → mutagen.wave.Wave

读取失败抛 AudioMetadataError（service 层捕获得 6002，recording 标 failed）。
"""
from __future__ import annotations

from io import BytesIO


class AudioMetadataError(Exception):
    """音频元数据读取失败（practice.md §6.3 → 6002）。"""


def read_duration_seconds(data: bytes, *, mime_type: str) -> int:
    """从音频字节流读取时长（秒，向下取整，ADR-020）。

    Args:
        data: 音频文件二进制内容
        mime_type: audio/webm | audio/mp4 | audio/mpeg | audio/wav

    Returns:
        duration_seconds（int，≥1，避免 0 时长录音污染统计）

    Raises:
        AudioMetadataError: 元数据读取失败或格式不支持
    """
    try:
        bio = BytesIO(data)
        length = _dispatch(bio, mime_type)
    except AudioMetadataError:
        raise
    except Exception as exc:  # mutagen 各类解析异常统一捕获
        raise AudioMetadataError(
            f"failed to read audio metadata for {mime_type}: {exc}"
        ) from exc

    if length is None or length < 0:
        raise AudioMetadataError(f"no duration metadata for {mime_type}")

    # 向下取整，最小 1 秒（避免 0 时长录音）
    seconds = int(length)
    return max(seconds, 1)


def _dispatch(bio: BytesIO, mime_type: str) -> float | None:
    """按 mime_type 分派到 mutagen 对应解析器。"""
    if mime_type == "audio/wav":
        return _read_wav(bio)
    if mime_type == "audio/mp4":
        return _read_mp4(bio)
    if mime_type == "audio/mpeg":
        return _read_mpeg(bio)
    if mime_type == "audio/webm":
        return _read_webm(bio)
    raise AudioMetadataError(f"unsupported mime_type: {mime_type}")


def _read_wav(bio: BytesIO) -> float | None:
    from mutagen.wave import Wave  # noqa: PLC0415

    audio = Wave(bio)
    return float(audio.info.length) if audio.info else None


def _read_mp4(bio: BytesIO) -> float | None:
    from mutagen.mp4 import MP4  # noqa: PLC0415

    audio = MP4(bio)
    return float(audio.info.length) if audio.info else None


def _read_mpeg(bio: BytesIO) -> float | None:
    from mutagen.mp3 import MP3  # noqa: PLC0415

    audio = MP3(bio)
    return float(audio.info.length) if audio.info else None


def _read_webm(bio: BytesIO) -> float | None:
    from mutagen.easywebm import EasyWebM  # noqa: PLC0415

    audio = EasyWebM(bio)
    return float(audio.info.length) if audio.info else None


__all__ = ["AudioMetadataError", "read_duration_seconds"]
