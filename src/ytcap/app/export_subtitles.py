"""Subtitle export use case."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ytcap.errors import ErrorCode, YtcapError
from ytcap.exporters.jsonl_writer import write_cue_jsonl_file, write_sentence_jsonl_file
from ytcap.exporters.output_paths import normalized_file_path
from ytcap.models.subtitle import SubtitleCue, SubtitleSentence
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
    category = _category_value(options.category)
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
    metadata_enrichment = _metadata_enrichment_for_job(job)
    metadata_enrichment.update(_category_enrichment(category))
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


def _metadata_enrichment_for_job(job: _ExportSubtitleJob) -> dict[str, Any]:
    metadata_path = _metadata_json_path(
        job.input_path,
        output_path=job.output_path,
        video_id=str(job.metadata.video_id),
    )
    metadata = _read_metadata_json(metadata_path)
    video = _dict_field(metadata, "video")
    channel = _dict_field(metadata, "channel")
    subtitles = _list_field(metadata, "subtitles")
    return {
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


def _metadata_json_path(path: Path, *, output_path: Path, video_id: str) -> Path:
    if path.parent.name == "subtitles":
        return path.parent.parent / "videos" / f"{video_id}.info.json"
    if output_path.parent.name == "normalized":
        return output_path.parent.parent / "videos" / f"{video_id}.info.json"
    return Path("data") / "videos" / f"{video_id}.info.json"


def _read_metadata_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"metadata file not found '{path}'",
            exit_code=2,
        ) from exc
    except OSError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"could not read metadata file '{path}': {exc}",
            exit_code=2,
        ) from exc
    except json.JSONDecodeError as exc:
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"could not parse metadata JSON '{path}': {exc}",
            exit_code=3,
        ) from exc

    if not isinstance(payload, dict):
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"metadata JSON must be an object '{path}'",
            exit_code=3,
        )
    return payload


def _dict_field(data: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = data.get(field_name)
    return value if isinstance(value, dict) else {}


def _list_field(data: dict[str, Any], field_name: str) -> list[Any]:
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
            if isinstance(item, dict)
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


def _category_value(category: str | None) -> str | None:
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


def _category_enrichment(category: str | None) -> dict[str, str]:
    if category is None:
        return {}
    return {
        "dataset_category": category,
        "category_source": "user",
    }


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
