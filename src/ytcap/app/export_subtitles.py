"""Subtitle export use case."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ytcap.errors import ErrorCode, YtcapError
from ytcap.exporters.jsonl_writer import write_cue_jsonl_file, write_sentence_jsonl_file
from ytcap.exporters.output_paths import infer_export_output_layout, normalized_file_path
from ytcap.models.export_enrichment import export_enrichment_fields, normalize_dataset_category
from ytcap.models.subtitle import SubtitleCue, SubtitleSentence
from ytcap.services.metadata_reader import read_metadata_json
from ytcap.services.subtitle_parser import parse_srt_file, parse_vtt_file
from ytcap.services.subtitle_segmenter import segment_cues_into_sentences


SUPPORTED_SUBTITLE_SUFFIXES = (".srt", ".vtt")
SUPPORTED_SEGMENTS = ("cue", "sentence")
KNOWN_SOURCES = ("manual", "auto")


@dataclass(frozen=True)
class ExportSubtitlesOptions:
    input_path: str | Path
    segments: str
    output_dir: str | Path
    video_id: str | None = None
    language: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class ExportedSubtitleFile:
    input_path: Path
    output_path: Path
    video_id: str
    language: str
    source: str
    segment_count: int


@dataclass(frozen=True)
class ExportSubtitlesResult:
    files: tuple[ExportedSubtitleFile, ...]


@dataclass(frozen=True)
class _SubtitleFileMetadata:
    video_id: str | None
    language: str | None
    source: str


@dataclass(frozen=True)
class _ExportSubtitleJob:
    input_path: Path
    output_path: Path
    metadata: _SubtitleFileMetadata


@dataclass(frozen=True)
class _PreparedSubtitleExport:
    job: _ExportSubtitleJob
    cues: tuple[SubtitleCue, ...]
    sentences: tuple[SubtitleSentence, ...] | None
    metadata_enrichment: dict[str, Any]
    segment_count: int


def export_subtitles(options: ExportSubtitlesOptions) -> ExportSubtitlesResult:
    _validate_segments(options.segments)
    category = normalize_dataset_category(options.category)
    input_path = Path(options.input_path)
    subtitle_files = _subtitle_files(input_path, options=options)
    output_dir = Path(options.output_dir)
    jobs = _export_jobs(subtitle_files, output_dir=output_dir, options=options)
    _validate_output_paths(jobs)
    prepared_exports = tuple(
        _prepare_subtitle_export(job, segments=options.segments, category=category)
        for job in jobs
    )

    exported_files = tuple(
        _write_prepared_export(prepared, segments=options.segments)
        for prepared in prepared_exports
    )
    return ExportSubtitlesResult(files=exported_files)


def _subtitle_files(input_path: Path, *, options: ExportSubtitlesOptions) -> tuple[Path, ...]:
    if not input_path.exists():
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"input path does not exist '{input_path}'",
            exit_code=2,
        )

    if input_path.is_file():
        _validate_supported_file(input_path)
        return (input_path,)

    if input_path.is_dir():
        if options.video_id or options.language:
            raise YtcapError(
                ErrorCode.INVALID_INPUT,
                "--video-id and --lang can only be used with a single subtitle file",
                exit_code=2,
            )
        try:
            files = tuple(
                sorted(
                    path
                    for path in input_path.iterdir()
                    if path.is_file() and _is_supported_subtitle_file(path)
                )
            )
        except OSError as exc:
            raise YtcapError(
                ErrorCode.INVALID_INPUT,
                f"could not read input directory '{input_path}': {exc}",
                exit_code=2,
            ) from exc
        if not files:
            raise YtcapError(
                ErrorCode.INVALID_INPUT,
                f"no SRT/VTT subtitle files found in directory '{input_path}'",
                exit_code=2,
            )
        return files

    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        f"input path is not a file or directory '{input_path}'",
        exit_code=2,
    )


def _export_jobs(
    subtitle_files: tuple[Path, ...],
    *,
    output_dir: Path,
    options: ExportSubtitlesOptions,
) -> tuple[_ExportSubtitleJob, ...]:
    jobs: list[_ExportSubtitleJob] = []
    for path in subtitle_files:
        metadata = _metadata_for_path(path, options=options)
        output_path = normalized_file_path(
            output_dir,
            video_id=str(metadata.video_id),
            language=str(metadata.language),
            segments=options.segments,
        )
        jobs.append(
            _ExportSubtitleJob(
                input_path=path,
                output_path=output_path,
                metadata=metadata,
            )
        )
    return tuple(jobs)


def _validate_output_paths(jobs: tuple[_ExportSubtitleJob, ...]) -> None:
    seen: dict[Path, Path] = {}
    for job in jobs:
        existing_input_path = seen.get(job.output_path)
        if existing_input_path is not None:
            raise YtcapError(
                ErrorCode.INVALID_INPUT,
                (
                    f"multiple subtitle files map to the same output file '{job.output_path}': "
                    f"'{existing_input_path}' and '{job.input_path}'"
                ),
                exit_code=2,
            )
        seen[job.output_path] = job.input_path

    for job in jobs:
        if job.output_path.exists():
            raise YtcapError(
                ErrorCode.OUTPUT_WRITE_FAILED,
                (
                    f"output file already exists '{job.output_path}'; "
                    "remove it or choose another --out directory"
                ),
                exit_code=5,
            )


def _prepare_subtitle_export(
    job: _ExportSubtitleJob,
    *,
    segments: str,
    category: str | None,
) -> _PreparedSubtitleExport:
    metadata_enrichment = _metadata_enrichment_for_job(job, category=category)
    cues = tuple(_parse_subtitle_file(job.input_path))
    if segments == "cue":
        return _PreparedSubtitleExport(
            job=job,
            cues=cues,
            sentences=None,
            metadata_enrichment=metadata_enrichment,
            segment_count=len(cues),
        )

    sentences = tuple(segment_cues_into_sentences(cues))
    return _PreparedSubtitleExport(
        job=job,
        cues=cues,
        sentences=sentences,
        metadata_enrichment=metadata_enrichment,
        segment_count=len(sentences),
    )


def _write_prepared_export(
    prepared: _PreparedSubtitleExport,
    *,
    segments: str,
) -> ExportedSubtitleFile:
    job = prepared.job
    metadata = job.metadata

    if segments == "cue":
        write_cue_jsonl_file(
            job.output_path,
            prepared.cues,
            video_id=str(metadata.video_id),
            language=str(metadata.language),
            source=metadata.source,
            metadata_enrichment=prepared.metadata_enrichment,
        )
    else:
        sentences = prepared.sentences or ()
        write_sentence_jsonl_file(
            job.output_path,
            sentences,
            video_id=str(metadata.video_id),
            language=str(metadata.language),
            source=metadata.source,
            metadata_enrichment=prepared.metadata_enrichment,
        )

    return ExportedSubtitleFile(
        input_path=job.input_path,
        output_path=job.output_path,
        video_id=str(metadata.video_id),
        language=str(metadata.language),
        source=metadata.source,
        segment_count=prepared.segment_count,
    )


def _metadata_for_path(path: Path, *, options: ExportSubtitlesOptions) -> _SubtitleFileMetadata:
    inferred = _infer_metadata_from_filename(path)
    metadata = _SubtitleFileMetadata(
        video_id=options.video_id or inferred.video_id,
        language=options.language or inferred.language,
        source=inferred.source,
    )
    if metadata.video_id and metadata.language:
        return metadata

    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        (
            f"could not infer video id and language from subtitle file '{path.name}'; "
            "expected VIDEO_ID.lang[.source].srt/vtt"
        ),
        exit_code=2,
    )


def _infer_metadata_from_filename(path: Path) -> _SubtitleFileMetadata:
    parts = path.stem.split(".")
    if len(parts) < 2:
        return _SubtitleFileMetadata(video_id=None, language=None, source="unknown")

    if len(parts) >= 3:
        source_candidate = parts[-1].lower()
        source = source_candidate if source_candidate in KNOWN_SOURCES else "unknown"
        return _SubtitleFileMetadata(
            video_id=".".join(parts[:-2]),
            language=parts[-2],
            source=source,
        )

    return _SubtitleFileMetadata(video_id=parts[0], language=parts[1], source="unknown")


def _metadata_enrichment_for_job(job: _ExportSubtitleJob, *, category: str | None) -> dict[str, Any]:
    layout = infer_export_output_layout(job.input_path, job.output_path.parent)
    metadata = read_metadata_json(layout.metadata_path(str(job.metadata.video_id)))
    return export_enrichment_fields(metadata, category=category)


def _parse_subtitle_file(path: Path) -> list[SubtitleCue]:
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return parse_srt_file(path)
    if suffix == ".vtt":
        return parse_vtt_file(path)
    _raise_unsupported_file(path)


def _validate_segments(segments: str) -> None:
    if segments in SUPPORTED_SEGMENTS:
        return
    supported = ", ".join(SUPPORTED_SEGMENTS)
    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        f"unsupported segment type '{segments}'; supported segments: {supported}",
        exit_code=2,
    )


def _validate_supported_file(path: Path) -> None:
    if _is_supported_subtitle_file(path):
        return
    _raise_unsupported_file(path)


def _is_supported_subtitle_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_SUBTITLE_SUFFIXES


def _raise_unsupported_file(path: Path) -> None:
    supported = ", ".join(SUPPORTED_SUBTITLE_SUFFIXES)
    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        f"unsupported subtitle file extension '{path.suffix}'; supported extensions: {supported}",
        exit_code=2,
    )
