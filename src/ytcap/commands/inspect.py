"""Inspect command skeleton."""

from __future__ import annotations

import json
from argparse import ArgumentParser, Namespace
from collections import defaultdict

from ytcap.models.video_metadata import inspect_payload, normalize_video_metadata
from ytcap.services.ytdlp_adapter import VideoSource, YtDlpAdapter

from .common import require_video_source


def configure_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--url", help="YouTube video URL")
    parser.add_argument("--id", dest="video_id", help="YouTube video ID")
    parser.add_argument("--list-subs", action="store_true", help="list subtitles in detail")
    parser.add_argument("--json", action="store_true", help="emit inspect output as JSON")
    parser.set_defaults(handler=handle)


def handle(args: Namespace) -> int:
    require_video_source(args)
    raw = YtDlpAdapter().extract_metadata(VideoSource(url=args.url, video_id=args.video_id))
    metadata = normalize_video_metadata(raw)
    payload = inspect_payload(metadata)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human_summary(payload, list_subs=args.list_subs)
    return 0


def _print_human_summary(payload: dict[str, object], *, list_subs: bool = False) -> None:
    print("Video")
    print(f"  ID: {payload['video_id']}")
    print(f"  Title: {payload['title']}")
    duration = payload["duration_seconds"]
    print(f"  Duration: {duration}s" if duration is not None else "  Duration: unknown")
    print()
    print("Subtitles")
    if list_subs:
        _print_subtitle_details(payload)
        return

    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for item in payload["subtitles"]:
        if isinstance(item, dict):
            grouped[str(item["language"])].append(str(item["source"]))
    if not grouped:
        print("  (none)")
        return
    for language, sources in sorted(grouped.items()):
        print(f"  {language}: {', '.join(sorted(sources))}")


def _print_subtitle_details(payload: dict[str, object]) -> None:
    items = [item for item in payload["subtitles"] if isinstance(item, dict)]
    if not items:
        print("  (none)")
        return

    for item in sorted(items, key=lambda value: (str(value["language"]), str(value["source"]))):
        formats = item.get("formats")
        format_text = ", ".join(formats) if isinstance(formats, list) and formats else "unknown"
        print(f"  {item['language']} {item['source']}: {format_text}")
