"""Normalize raw yt-dlp metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


SCHEMA_VERSION = "0.1"


def normalize_video_metadata(raw: dict[str, Any], *, fetched_at: datetime | None = None) -> dict[str, Any]:
    fetched = fetched_at or datetime.now(UTC)
    video_id = raw.get("id")
    url = f"https://www.youtube.com/watch?v={video_id}" if video_id else raw.get("webpage_url")

    return {
        "schema_version": SCHEMA_VERSION,
        "video": {
            "id": video_id,
            "url": url,
            "webpage_url": raw.get("webpage_url"),
            "title": raw.get("title"),
            "description": raw.get("description"),
            "duration_seconds": raw.get("duration"),
            "duration_text": raw.get("duration_string") or _format_duration(raw.get("duration")),
            "upload_date": raw.get("upload_date"),
            "timestamp": raw.get("timestamp"),
        },
        "channel": {
            "id": raw.get("channel_id") or raw.get("uploader_id"),
            "name": raw.get("channel") or raw.get("uploader"),
            "url": raw.get("channel_url") or raw.get("uploader_url"),
        },
        "media": {
            "availability": raw.get("availability"),
            "live_status": raw.get("live_status"),
            "thumbnail": raw.get("thumbnail"),
            "tags": raw.get("tags") or [],
        },
        "subtitles": _normalize_subtitles(raw),
        "extraction": {
            "tool": "ytcap",
            "extractor": "yt-dlp",
            "fetched_at": fetched.isoformat().replace("+00:00", "Z"),
            "status": "ok",
            "warnings": [],
        },
    }


def inspect_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    video = metadata["video"]
    return {
        "video_id": video["id"],
        "title": video["title"],
        "duration_seconds": video["duration_seconds"],
        "subtitles": [
            {
                "language": item["language"],
                "source": item["source"],
                "formats": item["formats"],
            }
            for item in metadata["subtitles"]
        ],
    }


def _normalize_subtitles(raw: dict[str, Any]) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    tracks.extend(_track_items(raw.get("subtitles"), "manual"))
    tracks.extend(_track_items(raw.get("automatic_captions"), "auto"))
    return tracks


def _track_items(collection: Any, source: str) -> list[dict[str, Any]]:
    if not isinstance(collection, dict):
        return []

    items: list[dict[str, Any]] = []
    for language, formats in sorted(collection.items()):
        items.append(
            {
                "language": language,
                "source": source,
                "formats": _format_list(formats),
                "selected": False,
                "downloaded": False,
                "path": None,
            }
        )
    return items


def _format_list(formats: Any) -> list[str]:
    if not isinstance(formats, list):
        return []
    values = sorted({item.get("ext") for item in formats if isinstance(item, dict) and item.get("ext")})
    return values


def _format_duration(duration: Any) -> str | None:
    if not isinstance(duration, int | float):
        return None
    total_seconds = int(duration)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"
