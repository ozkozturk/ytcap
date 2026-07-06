"""Single-video processing use case."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ytcap.errors import ErrorCode, YtcapError
from ytcap.exporters.json_writer import write_json_file
from ytcap.exporters.output_paths import build_output_layout, ensure_output_layout
from ytcap.models.video_metadata import normalize_video_metadata
from ytcap.services.subtitle_selector import select_subtitle_track
from ytcap.services.ytdlp_adapter import VideoSource


class VideoProcessingAdapter(Protocol):
    def extract_metadata(self, source: VideoSource) -> dict[str, Any]:
        ...

    def download_subtitle(
        self,
        source: VideoSource,
        *,
        language: str,
        subtitle_source: str,
        subtitle_format: str,
        output_path: str | Path,
    ) -> Path:
        ...


@dataclass(frozen=True)
class ProcessVideoOptions:
    url: str | None
    video_id: str | None
    language: str
    source: str
    subtitle_format: str
    output_dir: str | Path
    metadata_only: bool = False
    subs_only: bool = False
    skip_existing: bool = False
    overwrite: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class ProcessVideoResult:
    video_id: str
    metadata_path: Path | None
    subtitle_path: Path | None
    selected_source: str | None
    subtitle_requested: bool = True
    wrote_metadata: bool = False
    wrote_subtitle: bool = False
    skipped_metadata: bool = False
    skipped_subtitle: bool = False
    dry_run: bool = False


def process_video(options: ProcessVideoOptions, *, adapter: VideoProcessingAdapter) -> ProcessVideoResult:
    source = VideoSource(url=options.url, video_id=options.video_id)
    if options.dry_run:
        return _dry_run_result(options)

    layout = ensure_output_layout(options.output_dir)
    raw = adapter.extract_metadata(source)
    metadata = normalize_video_metadata(raw)
    video_id = _metadata_video_id(metadata, fallback=options.video_id)
    metadata_path = None if options.subs_only else layout.metadata_path(video_id)
    wrote_metadata = False
    skipped_metadata = False

    if metadata_path is not None:
        wrote_metadata = write_json_file(
            metadata_path,
            metadata,
            skip_existing=options.skip_existing,
            overwrite=options.overwrite,
        )
        skipped_metadata = not wrote_metadata

    subtitle_path: Path | None = None
    selected_source: str | None = None
    wrote_subtitle = False
    skipped_subtitle = False

    if not options.metadata_only:
        selected = select_subtitle_track(
            metadata["subtitles"],
            language=options.language,
            source=options.source,
            subtitle_format=options.subtitle_format,
        )
        selected_source = str(selected["source"])
        subtitle_path = layout.subtitle_path(video_id, options.language, selected_source, options.subtitle_format)

        if not _should_write_output(subtitle_path, options=options):
            skipped_subtitle = True
        else:
            adapter.download_subtitle(
                source,
                language=options.language,
                subtitle_source=selected_source,
                subtitle_format=options.subtitle_format,
                output_path=subtitle_path,
            )
            wrote_subtitle = True

        _mark_selected_subtitle(metadata, selected, downloaded=True, path=subtitle_path)
        if metadata_path is not None and not skipped_metadata:
            write_json_file(metadata_path, metadata, overwrite=True)

    return ProcessVideoResult(
        video_id=video_id,
        metadata_path=metadata_path,
        subtitle_path=subtitle_path,
        selected_source=selected_source,
        subtitle_requested=not options.metadata_only,
        wrote_metadata=wrote_metadata,
        wrote_subtitle=wrote_subtitle,
        skipped_metadata=skipped_metadata,
        skipped_subtitle=skipped_subtitle,
    )


def _dry_run_result(options: ProcessVideoOptions) -> ProcessVideoResult:
    layout = build_output_layout(options.output_dir)
    video_id = options.video_id or "VIDEO_ID"
    metadata_path = None if options.subs_only else layout.metadata_path(video_id)
    subtitle_path = None
    selected_source = None
    if not options.metadata_only and options.source in {"manual", "auto"}:
        selected_source = options.source
        subtitle_path = layout.subtitle_path(video_id, options.language, selected_source, options.subtitle_format)

    return ProcessVideoResult(
        video_id=video_id,
        metadata_path=metadata_path,
        subtitle_path=subtitle_path,
        selected_source=selected_source,
        subtitle_requested=not options.metadata_only,
        dry_run=True,
    )


def _metadata_video_id(metadata: dict[str, Any], *, fallback: str | None) -> str:
    video = metadata.get("video")
    video_id = video.get("id") if isinstance(video, dict) else None
    if isinstance(video_id, str) and video_id:
        return video_id
    if fallback:
        return fallback
    raise YtcapError(
        ErrorCode.PARSE_FAILED,
        "extracted metadata did not include a video id",
        exit_code=3,
    )


def _should_write_output(path: Path, *, options: ProcessVideoOptions) -> bool:
    if not path.exists():
        return True
    if options.skip_existing:
        return False
    if not options.overwrite:
        raise YtcapError(
            ErrorCode.OUTPUT_WRITE_FAILED,
            f"output file already exists '{path}'; use --overwrite or --skip-existing",
            exit_code=5,
        )
    return True


def _mark_selected_subtitle(
    metadata: dict[str, Any],
    selected: dict[str, Any],
    *,
    downloaded: bool,
    path: Path,
) -> None:
    for item in metadata["subtitles"]:
        if (
            item.get("language") == selected.get("language")
            and item.get("source") == selected.get("source")
            and item.get("formats") == selected.get("formats")
        ):
            item["selected"] = True
            item["downloaded"] = downloaded
            item["path"] = str(path)
        else:
            item["selected"] = False
