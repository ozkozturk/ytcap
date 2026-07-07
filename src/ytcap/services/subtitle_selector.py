"""Select subtitle tracks from normalized metadata."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.subtitle_format import validate_subtitle_format
from ytcap.services.subtitle_language import subtitle_language_match_rank


def select_subtitle_track(
    tracks: Sequence[dict[str, Any]],
    *,
    language: str,
    source: str,
    subtitle_format: str,
) -> dict[str, Any]:
    """Return a selected copy of the best matching subtitle track."""

    requested_format = validate_subtitle_format(subtitle_format)
    for preferred_source in _source_order(source):
        candidates: list[tuple[int, int, dict[str, Any]]] = []
        for index, track in enumerate(tracks):
            match_rank = _track_match_rank(
                track,
                language=language,
                source=preferred_source,
                subtitle_format=requested_format,
            )
            if match_rank is not None:
                candidates.append((match_rank, index, track))
        if candidates:
            _, _, track = min(candidates, key=lambda item: (item[0], item[1]))
            selected = dict(track)
            formats = selected.get("formats")
            if isinstance(formats, list):
                selected["formats"] = list(formats)
            selected["selected"] = True
            return selected

    raise YtcapError(
        ErrorCode.SUBTITLE_NOT_FOUND,
        f"subtitle not found for language '{language}', source '{source}', and format '{requested_format}'",
        exit_code=4,
        details={
            "language": language,
            "source": source,
            "format": requested_format,
        },
    )


def _source_order(source: str) -> tuple[str, ...]:
    if source == "any":
        return ("manual", "auto")
    if source in {"manual", "auto"}:
        return (source,)
    raise YtcapError(ErrorCode.INVALID_INPUT, f"unsupported subtitle source '{source}'", exit_code=2)


def _track_match_rank(
    track: dict[str, Any],
    *,
    language: str,
    source: str,
    subtitle_format: str,
) -> int | None:
    formats = track.get("formats")
    if track.get("source") != source or not isinstance(formats, list) or subtitle_format not in formats:
        return None
    return subtitle_language_match_rank(language, track.get("language"))
