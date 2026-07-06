"""Subtitle format validation helpers."""

from __future__ import annotations

from ytcap.errors import ErrorCode, YtcapError


SUPPORTED_SUBTITLE_FORMATS = ("srt", "vtt")


def validate_subtitle_format(subtitle_format: str) -> str:
    if subtitle_format in SUPPORTED_SUBTITLE_FORMATS:
        return subtitle_format

    supported = ", ".join(SUPPORTED_SUBTITLE_FORMATS)
    raise YtcapError(
        ErrorCode.UNSUPPORTED_FORMAT,
        f"unsupported subtitle format '{subtitle_format}'; supported formats: {supported}",
        exit_code=2,
    )
