"""Batch video processing use case."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ytcap.app.process_video import ProcessVideoOptions, process_video, VideoProcessingAdapter
from ytcap.errors import ErrorCode, YtcapError
from ytcap.exporters.failed_writer import append_failed_record
from ytcap.exporters.json_writer import write_json_file
from ytcap.exporters.output_paths import OutputLayout, build_output_layout, ensure_output_layout
from ytcap.services.batch_parser import parse_batch_file
from ytcap.services.ytdlp_adapter import VideoSource


@dataclass(frozen=True)
class ProcessBatchOptions:
    input: str | Path
    language: str
    source: str
    subtitle_format: str
    output_dir: str | Path
    resume: bool = False
    skip_existing: bool = False
    fail_fast: bool = False
    max_errors: int | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class ProcessBatchResult:
    run_id: str
    started_at: str
    finished_at: str
    total: int
    ok: int
    skipped: int
    failed: int
    manifest_path: Path


def _extract_video_id(source: VideoSource) -> str | None:
    if source.video_id:
        return source.video_id
    if source.url:
        match = re.search(r'(?:v=|\/embed\/|\/v\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', source.url)
        if match:
            return match.group(1)
    return None


def _is_already_processed(video_id: str, options: ProcessBatchOptions, layout: OutputLayout) -> bool:
    meta_path = layout.metadata_path(video_id)
    if not meta_path.exists():
        return False
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        subtitles = meta.get("subtitles", [])
        for track in subtitles:
            if track.get("selected") and track.get("downloaded"):
                sub_path_str = track.get("path")
                if sub_path_str and Path(sub_path_str).exists():
                    return True
        return False
    except Exception:
        return False


def process_batch(options: ProcessBatchOptions, *, adapter: VideoProcessingAdapter) -> ProcessBatchResult:
    if options.max_errors is not None and options.max_errors < 1:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "--max-errors must be a positive integer",
            exit_code=2,
        )

    sources = parse_batch_file(options.input)
    if not sources:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            "batch input file did not contain any video URLs or IDs",
            exit_code=2,
        )

    layout = build_output_layout(options.output_dir) if options.dry_run else ensure_output_layout(options.output_dir)

    started_at = datetime.now(UTC)
    started_at_str = started_at.isoformat().replace("+00:00", "Z")
    run_id = started_at_str.replace(":", "-")

    completed_ids: set[str] = set()
    prev_manifest: dict[str, Any] | None = None
    outputs: list[str] = []
    errors: list[dict[str, Any]] = []

    total = len(sources)
    ok_count = 0
    skipped_count = 0
    failed_count = 0

    if options.resume:
        manifest_files = sorted(layout.runs_dir.glob("*.manifest.json"))
        if manifest_files:
            latest_manifest_path = manifest_files[-1]
            try:
                with open(latest_manifest_path, "r", encoding="utf-8") as f:
                    prev_manifest = json.load(f)
                run_id = prev_manifest.get("run_id", run_id)
                started_at_str = prev_manifest.get("started_at", started_at_str)
                outputs = prev_manifest.get("outputs", [])
                prev_summary = prev_manifest.get("summary", {})
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
            "command": "batch",
            "input": {
                "type": "file",
                "path": str(options.input),
            },
            "options": {
                "language": options.language,
                "source": options.source,
                "format": options.subtitle_format,
                "skip_existing": options.skip_existing,
            },
            "summary": {
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
        for source in sources:
            video_id = _extract_video_id(source) or "VIDEO_ID"
            if video_id in completed_ids:
                continue
            if options.skip_existing and video_id != "VIDEO_ID" and _is_already_processed(video_id, options, layout):
                skipped_count += 1
            else:
                ok_count += 1

        finished_at_str = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        return ProcessBatchResult(
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
        for source in sources:
            video_id = _extract_video_id(source)

            if video_id and video_id in completed_ids:
                continue

            if options.skip_existing and video_id and _is_already_processed(video_id, options, layout):
                skipped_count += 1
                meta_path = layout.metadata_path(video_id)
                if str(meta_path) not in outputs:
                    outputs.append(str(meta_path))
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    for track in meta.get("subtitles", []):
                        if track.get("selected") and track.get("downloaded") and track.get("path"):
                            if track["path"] not in outputs:
                                outputs.append(track["path"])
                except Exception:
                    pass
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
                        f"batch aborted after reaching {options.max_errors} errors",
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
                        f"batch aborted after reaching {options.max_errors} errors",
                        exit_code=1,
                    )

            write_manifest(datetime.now(UTC))

    finally:
        if not options.dry_run:
            write_manifest(datetime.now(UTC))

    finished_at_str = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return ProcessBatchResult(
        run_id=run_id,
        started_at=started_at_str,
        finished_at=finished_at_str,
        total=total,
        ok=ok_count,
        skipped=skipped_count,
        failed=failed_count,
        manifest_path=manifest_path,
    )
