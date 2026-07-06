"""Select subtitle tracks from normalized metadata."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ytcap.errors import ErrorCode, YtcapError


def select_subtitle_track(
    tracks: Sequence[dict[str, Any]],
    *,
    language: str,
    source: str,
    subtitle_format: str,
) -> dict[str, Any]:
    """Return a selected copy of the best matching subtitle track."""

    for preferred_source in _source_order(source):
        for track in tracks:
            if _matches_track(
                track,
                language=language,
                source=preferred_source,
                subtitle_format=subtitle_format,
            ):
                selected = dict(track)
                formats = selected.get("formats")
                if isinstance(formats, list):
                    selected["formats"] = list(formats)
                selected["selected"] = True
                return selected

    raise YtcapError(
        ErrorCode.SUBTITLE_NOT_FOUND,
        f"subtitle not found for language '{language}', source '{source}', and format '{subtitle_format}'",
        exit_code=4,
    )


def _source_order(source: str) -> tuple[str, ...]:
    if source == "any":
        return ("manual", "auto")
    if source in {"manual", "auto"}:
        return (source,)
    raise YtcapError(ErrorCode.INVALID_INPUT, f"unsupported subtitle source '{source}'", exit_code=2)


def _matches_track(
    track: dict[str, Any],
    *,
    language: str,
    source: str,
    subtitle_format: str,
) -> bool:
    formats = track.get("formats")
    return (
        track.get("language") == language
        and track.get("source") == source
        and isinstance(formats, list)
        and subtitle_format in formats
    )
