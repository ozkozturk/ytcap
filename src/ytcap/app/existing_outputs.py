"""Helpers for recognizing completed video outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ytcap.exporters.output_paths import OutputLayout
from ytcap.services.subtitle_language import subtitle_language_match_rank


@dataclass(frozen=True)
class ExistingVideoOutput:
    metadata_path: Path
    subtitle_path: Path


def find_existing_video_output(
    video_id: str,
    *,
    layout: OutputLayout,
    language: str,
    source: str,
    subtitle_format: str,
) -> ExistingVideoOutput | None:
    """Return matching existing output for the requested subtitle selection."""
    meta_path = layout.metadata_path(video_id)
    if not meta_path.exists():
        return None

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    subtitles = meta.get("subtitles", [])
    if not isinstance(subtitles, list):
        return None

    for track in subtitles:
        if not _track_matches(track, language=language, source=source, subtitle_format=subtitle_format):
            continue
        subtitle_path = _existing_subtitle_path(track.get("path"), layout=layout)
        if subtitle_path is not None:
            return ExistingVideoOutput(metadata_path=meta_path, subtitle_path=subtitle_path)
    return None


def _track_matches(track: Any, *, language: str, source: str, subtitle_format: str) -> bool:
    if not isinstance(track, dict):
        return False
    if not track.get("selected") or not track.get("downloaded"):
        return False
    if subtitle_language_match_rank(language, track.get("language")) is None:
        return False
    track_source = track.get("source")
    if source == "any":
        if track_source not in {"manual", "auto"}:
            return False
    elif track_source != source:
        return False

    formats = track.get("formats")
    return isinstance(formats, list) and subtitle_format in formats


def _existing_subtitle_path(path_value: Any, *, layout: OutputLayout) -> Path | None:
    if not isinstance(path_value, str) or not path_value:
        return None

    subtitle_path = Path(path_value)
    if subtitle_path.exists():
        return subtitle_path

    rooted_path = layout.root / subtitle_path
    if rooted_path.exists():
        return rooted_path
    return None
