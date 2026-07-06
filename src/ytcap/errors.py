"""Shared error types for ytcap."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    VIDEO_UNAVAILABLE = "VIDEO_UNAVAILABLE"
    SUBTITLE_NOT_FOUND = "SUBTITLE_NOT_FOUND"
    YTDLP_NOT_AVAILABLE = "YTDLP_NOT_AVAILABLE"
    YTDLP_FAILED = "YTDLP_FAILED"
    OUTPUT_WRITE_FAILED = "OUTPUT_WRITE_FAILED"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    CONFLICTING_FLAGS = "CONFLICTING_FLAGS"
    PARSE_FAILED = "PARSE_FAILED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class YtcapError(Exception):
    """Base exception for controlled user-facing errors."""

    def __init__(self, code: ErrorCode, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


def format_error(error: YtcapError) -> str:
    return f"error: {error.message}\ncode: {error.code.value}"
