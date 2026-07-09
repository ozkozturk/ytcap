"""JSONL export enrichment fields."""

from __future__ import annotations

from typing import Any, Mapping

from ytcap.errors import ErrorCode, YtcapError


EXPORT_ENRICHMENT_DEFAULTS: dict[str, Any] = {
    "channel_id": None,
    "channel_name": None,
    "channel_url": None,
    "video_title": None,
    "video_url": None,
    "video_webpage_url": None,
    "video_duration_seconds": None,
    "video_upload_date": None,
    "available_manual_subtitles": None,
    "downloaded_subtitles": None,
    "dataset_category": None,
    "category_source": "none",
}


def export_enrichment_fields(metadata: Mapping[str, Any], *, category: str | None = None) -> dict[str, Any]:
    fields = dict(EXPORT_ENRICHMENT_DEFAULTS)
    video = _mapping_field(metadata, "video")
    channel = _mapping_field(metadata, "channel")
    subtitles = _list_field(metadata, "subtitles")

    fields.update(
        {
            "channel_id": channel.get("id"),
            "channel_name": channel.get("name"),
            "channel_url": channel.get("url"),
            "video_title": video.get("title"),
            "video_url": video.get("url"),
            "video_webpage_url": video.get("webpage_url"),
            "video_duration_seconds": video.get("duration_seconds"),
            "video_upload_date": video.get("upload_date"),
            "available_manual_subtitles": _subtitle_languages(
                subtitles,
                source="manual",
                downloaded=None,
            ),
            "downloaded_subtitles": _subtitle_languages(
                subtitles,
                source=None,
                downloaded=True,
            ),
        }
    )
    fields.update(_category_fields(category))
    return fields


def normalize_dataset_category(category: str | None) -> str | None:
    if category is None:
        return None
    value = category.strip()
    if value:
        return value
    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        "--category must not be empty",
        exit_code=2,
    )


def _category_fields(category: str | None) -> dict[str, str]:
    normalized_category = normalize_dataset_category(category)
    if normalized_category is None:
        return {}
    return {
        "dataset_category": normalized_category,
        "category_source": "user",
    }


def _mapping_field(data: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = data.get(field_name)
    return value if isinstance(value, Mapping) else {}


def _list_field(data: Mapping[str, Any], field_name: str) -> list[Any]:
    value = data.get(field_name)
    return value if isinstance(value, list) else []


def _subtitle_languages(
    subtitles: list[Any],
    *,
    source: str | None,
    downloaded: bool | None,
) -> list[str] | None:
    languages = sorted(
        {
            language
            for item in subtitles
            if isinstance(item, Mapping)
            if (source is None or item.get("source") == source)
            if (downloaded is None or item.get("downloaded") is downloaded)
            if isinstance((language := item.get("language")), str)
            if not _is_english_language(language)
        }
    )
    return languages or None


def _is_english_language(language: str) -> bool:
    normalized = language.casefold()
    return normalized == "en" or normalized.startswith("en-")
