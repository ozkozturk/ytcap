"""Shared command helpers."""

from __future__ import annotations

from argparse import Namespace

from ytcap.errors import ErrorCode, YtcapError


def require_video_source(args: Namespace) -> None:
    if getattr(args, "url", None) and getattr(args, "video_id", None):
        raise YtcapError(
            ErrorCode.CONFLICTING_FLAGS,
            "--url and --id cannot be used together",
            exit_code=2,
        )
    if not getattr(args, "url", None) and not getattr(args, "video_id", None):
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "one of --url or --id is required",
            exit_code=2,
        )


def display_video_source(args: Namespace) -> str:
    if getattr(args, "url", None):
        return f"url={args.url}"
    return f"id={args.video_id}"
