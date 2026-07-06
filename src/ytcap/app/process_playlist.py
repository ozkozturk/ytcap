"""Playlist processing use case."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ytcap.app.existing_outputs import find_existing_video_output
from ytcap.app.process_video import ProcessVideoOptions, VideoProcessingAdapter, process_video
from ytcap.errors import ErrorCode, YtcapError
from ytcap.exporters.failed_writer import append_failed_record
from ytcap.exporters.json_writer import write_json_file
from ytcap.exporters.output_paths import build_output_layout, ensure_output_layout
from ytcap.services.ytdlp_adapter import VideoSource


class PlaylistProcessingAdapter(VideoProcessingAdapter, Protocol):
    def extract_playlist_entries(self, source: VideoSource) -> list[VideoSource]:
        ...


@dataclass(frozen=True)
class ProcessPlaylistOptions:
    url: str
    language: str
    source: str
    subtitle_format: str
    output_dir: str | Path
    limit: int | None = None
    start: int = 1
    end: int | None = None
    skip_existing: bool = False
    fail_fast: bool = False
    max_errors: int | None = None
    resume: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class ProcessPlaylistResult:
    run_id: str
    started_at: str
    finished_at: str
    total: int
    ok: int
    skipped: int
    failed: int
    manifest_path: Path


def _extract_video_id_from_source(source: VideoSource) -> str | None:
    if source.video_id:
        return source.video_id
    if source.url:
        match = re.search(r'(?:v=|\/embed\/|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', source.url)
        if match:
            return match.group(1)
    return None


def _apply_range(
    entries: list[VideoSource],
    *,
    start: int = 1,
    end: int | None = None,
    limit: int | None = None,
) -> list[VideoSource]:
    if start > 1:
        entries = entries[start - 1:]
    if end is not None:
        entries = entries[:end - start + 1]
    if limit is not None and limit > 0:
        entries = entries[:limit]
    return entries


def _matching_resume_manifest(options: ProcessPlaylistOptions, manifest_files: list[Path]) -> dict[str, Any] | None:
    for manifest_path in sorted(manifest_files, reverse=True):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if _manifest_matches_playlist_options(manifest, options):
            return manifest
    return None


def _manifest_matches_playlist_options(manifest: dict[str, Any], options: ProcessPlaylistOptions) -> bool:
    if manifest.get("command") != "playlist":
        return False

    manifest_input = manifest.get("input")
    if not isinstance(manifest_input, dict) or manifest_input.get("url") != options.url:
        return False

    manifest_options = manifest.get("options")
    if not isinstance(manifest_options, dict):
        return False

    expected = {
        "language": options.language,
        "source": options.source,
        "format": options.subtitle_format,
        "limit": options.limit,
        "start": options.start,
        "end": options.end,
    }
    return all(manifest_options.get(key) == value for key, value in expected.items())


def process_playlist(
    options: ProcessPlaylistOptions,
    *,
    adapter: PlaylistProcessingAdapter,
) -> ProcessPlaylistResult:
    playlist_source = VideoSource(url=options.url)

    entries = adapter.extract_playlist_entries(playlist_source)

    if not entries:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "playlist did not contain any videos",
            exit_code=2,
        )

    entry_count = len(entries)
    entries = _apply_range(entries, start=options.start, end=options.end, limit=options.limit)
    total = len(entries)

    if total == 0:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "range or limit resulted in zero videos to process",
            exit_code=2,
        )

    layout = build_output_layout(options.output_dir) if options.dry_run else ensure_output_layout(options.output_dir)

    started_at = datetime.now(UTC)
    started_at_str = started_at.isoformat().replace("+00:00", "Z")
    run_id = started_at_str.replace(":", "-")

    completed_ids: set[str] = set()
    outputs: list[str] = []
    errors: list[dict[str, Any]] = []

    ok_count = 0
    skipped_count = 0
    failed_count = 0

    if options.resume:
        prev_manifest = _matching_resume_manifest(options, list(layout.runs_dir.glob("*.manifest.json")))
        if prev_manifest is not None:
            try:
                run_id = prev_manifest.get("run_id", run_id)
                started_at_str = prev_manifest.get("started_at", started_at_str)
                prev_outputs = prev_manifest.get("outputs", [])
                outputs = prev_outputs if isinstance(prev_outputs, list) else []
                prev_summary = prev_manifest.get("summary", {})
                if isinstance(prev_summary, dict):
                    ok_count = prev_summary.get("ok", 0)
                    skipped_count = prev_summary.get("skipped", 0)

                for out_path in outputs:
                    name = Path(out_path).name
                    match = re.match(r"([a-zA-Z0-9_-]{11})\.", name)
                    if match:
                        completed_ids.add(match.group(1))
            except Exception:
                pass

    manifest_path = layout.run_manifest_path(run_id)

    def write_manifest(finished_time: datetime) -> None:
        finished_at_str = finished_time.isoformat().replace("+00:00", "Z")
        manifest_data = {
            "schema_version": "0.1",
            "run_id": run_id,
            "started_at": started_at_str,
            "finished_at": finished_at_str,
            "command": "playlist",
            "input": {
                "type": "playlist",
                "url": options.url,
            },
            "options": {
                "language": options.language,
                "source": options.source,
                "format": options.subtitle_format,
                "skip_existing": options.skip_existing,
                "limit": options.limit,
                "start": options.start,
                "end": options.end,
            },
            "summary": {
                "playlist_entries": entry_count,
                "total": total,
                "ok": ok_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
            "outputs": outputs,
            "errors": errors,
        }
        write_json_file(manifest_path, manifest_data, overwrite=True)

    if options.dry_run:
        for source in entries:
            video_id = _extract_video_id_from_source(source)
            if video_id and video_id in completed_ids:
                continue
            existing_output = None
            if options.skip_existing and video_id:
                existing_output = find_existing_video_output(
                    video_id,
                    layout=layout,
                    language=options.language,
                    source=options.source,
                    subtitle_format=options.subtitle_format,
                )
            if existing_output is not None:
                skipped_count += 1
            else:
                ok_count += 1

        finished_at_str = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return ProcessPlaylistResult(
            run_id=run_id,
            started_at=started_at_str,
            finished_at=finished_at_str,
            total=total,
            ok=ok_count,
            skipped=skipped_count,
            failed=failed_count,
            manifest_path=manifest_path,
        )

    try:
        for source in entries:
            video_id = _extract_video_id_from_source(source)

            if video_id and video_id in completed_ids:
                continue

            existing_output = None
            if options.skip_existing and video_id:
                existing_output = find_existing_video_output(
                    video_id,
                    layout=layout,
                    language=options.language,
                    source=options.source,
                    subtitle_format=options.subtitle_format,
                )

            if existing_output is not None:
                skipped_count += 1
                if str(existing_output.metadata_path) not in outputs:
                    outputs.append(str(existing_output.metadata_path))
                if str(existing_output.subtitle_path) not in outputs:
                    outputs.append(str(existing_output.subtitle_path))
                write_manifest(datetime.now(UTC))
                continue

            video_options = ProcessVideoOptions(
                url=source.url,
                video_id=source.video_id,
                language=options.language,
                source=options.source,
                subtitle_format=options.subtitle_format,
                output_dir=options.output_dir,
                skip_existing=options.skip_existing,
                overwrite=False,
            )

            res: Any = None

            try:
                res = process_video(video_options, adapter=adapter)
                ok_count += 1

                if res.metadata_path and str(res.metadata_path) not in outputs:
                    outputs.append(str(res.metadata_path))
                if res.subtitle_path and str(res.subtitle_path) not in outputs:
                    outputs.append(str(res.subtitle_path))

            except YtcapError as exc:
                failed_count += 1
                v_id = video_id or (res.video_id if res else None)
                errors.append({
                    "video_id": v_id,
                    "code": exc.code.value,
                    "message": exc.message,
                })
                append_failed_record(
                    layout.failed_path(),
                    video_id=v_id,
                    url=source.url,
                    code=exc.code.value,
                    message=exc.message,
                )

                if options.fail_fast:
                    write_manifest(datetime.now(UTC))
                    raise exc

                if options.max_errors is not None and failed_count >= options.max_errors:
                    write_manifest(datetime.now(UTC))
                    raise YtcapError(
                        ErrorCode.YTDLP_FAILED,
                        f"playlist processing aborted after reaching {options.max_errors} errors",
                        exit_code=1,
                    )
            except Exception as exc:
                failed_count += 1
                v_id = video_id
                err_msg = str(exc)
                errors.append({
                    "video_id": v_id,
                    "code": ErrorCode.YTDLP_FAILED.value,
                    "message": err_msg,
                })
                append_failed_record(
                    layout.failed_path(),
                    video_id=v_id,
                    url=source.url,
                    code=ErrorCode.YTDLP_FAILED.value,
                    message=err_msg,
                )

                if options.fail_fast:
                    write_manifest(datetime.now(UTC))
                    raise YtcapError(
                        ErrorCode.YTDLP_FAILED,
                        err_msg,
                        exit_code=1,
                    ) from exc

                if options.max_errors is not None and failed_count >= options.max_errors:
                    write_manifest(datetime.now(UTC))
                    raise YtcapError(
                        ErrorCode.YTDLP_FAILED,
                        f"playlist processing aborted after reaching {options.max_errors} errors",
                        exit_code=1,
                    )

            write_manifest(datetime.now(UTC))

    finally:
        if not options.dry_run:
            write_manifest(datetime.now(UTC))

    finished_at_str = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return ProcessPlaylistResult(
        run_id=run_id,
        started_at=started_at_str,
        finished_at=finished_at_str,
        total=total,
        ok=ok_count,
        skipped=skipped_count,
        failed=failed_count,
        manifest_path=manifest_path,
    )
