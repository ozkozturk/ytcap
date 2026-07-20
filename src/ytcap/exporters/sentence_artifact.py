"""Deterministic sentence JSONL artifacts and companion manifests."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ytcap import __version__
from ytcap.errors import ErrorCode, YtcapError
from ytcap.exporters.jsonl_writer import (
    SCHEMA_VERSION as SENTENCE_SCHEMA_VERSION,
    sentence_jsonl_record,
    serialize_jsonl_records,
)
from ytcap.models.subtitle import SubtitleSentence
from ytcap.services.sentence_boundaries import BOUNDARY_ENGINE
from ytcap.services.sentence_timing import (
    PLAYBACK_END_PADDING_SECONDS,
    PLAYBACK_START_PADDING_SECONDS,
    TIME_QUANTUM_DECIMALS,
    TIMING_ESTIMATOR,
)
from ytcap.services.text_normalizer import normalize_search_text


MANIFEST_SCHEMA_VERSION = "0.1"
ARTIFACT_TYPE = "sentence_jsonl"
KNOWN_SOURCES = frozenset({"manual", "auto", "unknown"})
QUALITY_PRECISIONS = (
    "cue_aligned",
    "estimated_start",
    "estimated_end",
    "estimated_both",
    "unknown",
)
LONG_GAP_SECONDS = 10.0
LONG_SENTENCE_SECONDS = 30.0


def sentence_manifest_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.with_suffix(".manifest.json")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"could not hash artifact '{path}': {exc}",
            exit_code=2,
        ) from exc
    return digest.hexdigest()


def write_sentence_artifact(
    output_path: str | Path,
    sentences: Sequence[SubtitleSentence],
    *,
    source_path: str | Path,
    video_id: str,
    language: str,
    source: str,
    metadata_enrichment: Mapping[str, Any] | None = None,
    metadata_path: str | Path | None = None,
) -> Path:
    """Atomically publish a verified sentence JSONL/manifest pair."""

    destination = Path(output_path)
    manifest_path = sentence_manifest_path(destination)
    source_artifact = Path(source_path)
    metadata_artifact = Path(metadata_path) if metadata_path is not None else None
    _validate_identity(video_id=video_id, language=language, source=source)
    _ensure_destinations_absent(destination, manifest_path)

    records = [
        sentence_jsonl_record(
            sentence,
            video_id=video_id,
            language=language,
            source=source,
            metadata_enrichment=metadata_enrichment,
        )
        for sentence in sentences
    ]
    try:
        jsonl_bytes = serialize_jsonl_records(records)
    except (TypeError, ValueError) as exc:
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"sentence records are not valid deterministic JSON: {exc}",
            exit_code=3,
        ) from exc

    manifest = build_sentence_manifest(
        records,
        output_path=destination,
        output_bytes=jsonl_bytes,
        source_path=source_artifact,
        video_id=video_id,
        language=language,
        source=source,
        metadata_path=metadata_artifact,
    )
    manifest_bytes = _serialize_manifest(manifest)
    verify_sentence_artifact_bytes(jsonl_bytes, manifest)
    _publish_pair(destination, jsonl_bytes, manifest_path, manifest_bytes)
    try:
        verify_sentence_artifact(manifest_path)
    except YtcapError:
        _unlink_if_exists(destination)
        _unlink_if_exists(manifest_path)
        raise
    return manifest_path


def build_sentence_manifest(
    records: Sequence[Mapping[str, Any]],
    *,
    output_path: Path,
    output_bytes: bytes,
    source_path: Path,
    video_id: str,
    language: str,
    source: str,
    metadata_path: Path | None,
) -> dict[str, Any]:
    input_bytes = _read_bytes(source_path, label="source subtitle")
    metadata_bytes = (
        _read_bytes(metadata_path, label="metadata") if metadata_path is not None else None
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "producer": {"name": "ytcap", "version": __version__},
        "identity": {
            "video_id": video_id,
            "language": language,
            "source": source,
        },
        "segmentation": {
            "boundary_engine": BOUNDARY_ENGINE,
            "timing_estimator": TIMING_ESTIMATOR,
            "time_quantum_decimals": TIME_QUANTUM_DECIMALS,
        },
        "playback_hint": {
            "start_padding_seconds": PLAYBACK_START_PADDING_SECONDS,
            "end_padding_seconds": PLAYBACK_END_PADDING_SECONDS,
        },
        "input": {
            "filename": _logical_source_filename(source_path, output_path.parent),
            "format": source_path.suffix.lower().lstrip("."),
            "sha256": sha256_bytes(input_bytes),
        },
        "output": {
            "filename": output_path.name,
            "sha256": sha256_bytes(output_bytes),
            "record_count": len(records),
            "schema_version": SENTENCE_SCHEMA_VERSION,
        },
        "metadata": {
            "filename": _logical_metadata_filename(metadata_path, output_path.parent),
            "sha256": sha256_bytes(metadata_bytes) if metadata_bytes is not None else None,
        },
        "quality_summary": quality_summary(records),
    }


def quality_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    summary = {precision: 0 for precision in QUALITY_PRECISIONS}
    summary.update(
        {
            "empty_text": 0,
            "non_positive_duration": 0,
            "overlap_with_previous": 0,
            "large_gap": 0,
            "long_duration": 0,
        }
    )
    previous_end: float | None = None
    for record in records:
        precision = record.get("timing_precision")
        summary[precision if precision in QUALITY_PRECISIONS else "unknown"] += 1
        text = record.get("normalized_text")
        if not isinstance(text, str) or not text:
            summary["empty_text"] += 1
        start = record.get("start")
        end = record.get("end")
        if not _finite_number(start) or not _finite_number(end):
            summary["non_positive_duration"] += 1
            previous_end = None
            continue
        start_value = float(start)
        end_value = float(end)
        if end_value <= start_value:
            summary["non_positive_duration"] += 1
        if previous_end is not None:
            if start_value < previous_end:
                summary["overlap_with_previous"] += 1
            if start_value - previous_end > LONG_GAP_SECONDS:
                summary["large_gap"] += 1
        if end_value - start_value > LONG_SENTENCE_SECONDS:
            summary["long_duration"] += 1
        previous_end = end_value
    return summary


def verify_sentence_artifact(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    try:
        manifest_payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _verification_error(f"could not read manifest '{path}': {exc}")
    if not isinstance(manifest_payload, dict):
        _verification_error("manifest root must be a JSON object")
    manifest = manifest_payload
    output = _required_mapping(manifest, "output")
    output_filename = _required_logical_filename(output, "filename")
    output_path = _resolve_artifact_path(path, output_filename)
    jsonl_bytes = _read_bytes(output_path, label="sentence JSONL")
    verify_sentence_artifact_bytes(jsonl_bytes, manifest)

    input_artifact = _required_mapping(manifest, "input")
    input_filename = _required_logical_filename(input_artifact, "filename")
    input_path = _resolve_artifact_path(path, input_filename)
    if input_path.exists() and sha256_file(input_path) != input_artifact.get("sha256"):
        _verification_error("source subtitle SHA-256 does not match manifest")

    metadata = _required_mapping(manifest, "metadata")
    metadata_filename = metadata.get("filename")
    if metadata_filename is not None:
        if not isinstance(metadata_filename, str) or Path(metadata_filename).is_absolute():
            _verification_error("metadata filename must be logical/relative")
        metadata_path = _resolve_artifact_path(path, metadata_filename)
        if metadata_path.exists() and sha256_file(metadata_path) != metadata.get("sha256"):
            _verification_error("metadata SHA-256 does not match manifest")
    elif metadata.get("sha256") is not None:
        _verification_error("metadata SHA-256 must be null when filename is null")
    return manifest


def verify_sentence_artifact_bytes(
    jsonl_bytes: bytes,
    manifest: Mapping[str, Any],
) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        _verification_error("unsupported manifest schema_version")
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        _verification_error("manifest artifact_type must be sentence_jsonl")
    producer = _required_mapping(manifest, "producer")
    if (
        producer.get("name") != "ytcap"
        or not isinstance(producer.get("version"), str)
        or not producer.get("version")
    ):
        _verification_error("manifest producer identity is invalid")
    identity = _required_mapping(manifest, "identity")
    _validate_identity(
        video_id=identity.get("video_id"),
        language=identity.get("language"),
        source=identity.get("source"),
    )
    segmentation = _required_mapping(manifest, "segmentation")
    if segmentation.get("boundary_engine") != BOUNDARY_ENGINE:
        _verification_error("manifest boundary engine is invalid")
    if segmentation.get("timing_estimator") != TIMING_ESTIMATOR:
        _verification_error("manifest timing estimator is invalid")
    if segmentation.get("time_quantum_decimals") != TIME_QUANTUM_DECIMALS:
        _verification_error("manifest time quantum is invalid")
    playback_hint = _required_mapping(manifest, "playback_hint")
    if playback_hint.get("start_padding_seconds") != PLAYBACK_START_PADDING_SECONDS:
        _verification_error("manifest playback start padding is invalid")
    if playback_hint.get("end_padding_seconds") != PLAYBACK_END_PADDING_SECONDS:
        _verification_error("manifest playback end padding is invalid")

    output = _required_mapping(manifest, "output")
    _required_logical_filename(output, "filename")
    if sha256_bytes(jsonl_bytes) != output.get("sha256"):
        _verification_error("sentence JSONL SHA-256 does not match manifest")
    records = _parse_jsonl(jsonl_bytes)
    if output.get("record_count") != len(records):
        _verification_error("sentence JSONL record count does not match manifest")
    if output.get("schema_version") != SENTENCE_SCHEMA_VERSION:
        _verification_error("manifest output schema_version is invalid")
    _validate_records(records, identity=identity)
    if manifest.get("quality_summary") != quality_summary(records):
        _verification_error("quality summary does not match sentence records")


def _validate_records(
    records: Sequence[Mapping[str, Any]],
    *,
    identity: Mapping[str, Any],
) -> None:
    expected_index = 1
    for record in records:
        for field in ("video_id", "language", "source"):
            if record.get(field) != identity.get(field):
                _verification_error(f"mixed sentence artifact identity field: {field}")
        if record.get("schema_version") != SENTENCE_SCHEMA_VERSION:
            _verification_error("mixed sentence artifact schema_version")
        if record.get("type") != "sentence":
            _verification_error("sentence artifact contains a non-sentence row")
        if record.get("sentence_index") != expected_index:
            _verification_error("sentence_index values must be monotonic and start at 1")
        expected_index += 1
        for field in ("start", "end", "playback_start", "playback_end"):
            if not _finite_number(record.get(field)):
                _verification_error(f"sentence field {field} must be finite")
        if not isinstance(record.get("text"), str):
            _verification_error("sentence text must be a string")
        normalized_text = record.get("normalized_text")
        if not isinstance(normalized_text, str):
            _verification_error("sentence normalized_text must be a string")
        if normalized_text != normalize_search_text(record["text"]):
            _verification_error("sentence normalized_text is inconsistent with text")
        if record.get("boundary_engine") != BOUNDARY_ENGINE:
            _verification_error("mixed sentence artifact boundary_engine")
        if record.get("cue_coverage") not in {"single", "multiple"}:
            _verification_error("sentence cue_coverage is invalid")
        if record.get("timing_precision") not in QUALITY_PRECISIONS:
            _verification_error("sentence timing_precision is invalid")
        if record.get("timing_strategy") not in {
            "cue_exact",
            "cue_merge",
            "heuristic",
            "unknown",
        }:
            _verification_error("sentence timing_strategy is invalid")
        for field in ("start_cue_index", "end_cue_index"):
            value = record.get(field)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                _verification_error(f"sentence field {field} must be an integer or null")
        for field in ("cue_count", "start_char_in_first_cue", "end_char_in_last_cue"):
            value = record.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                _verification_error(f"sentence field {field} must be a non-negative integer")


def _parse_jsonl(payload: bytes) -> list[Mapping[str, Any]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        _verification_error(f"sentence JSONL must be UTF-8: {exc}")
    if text and not text.endswith("\n"):
        _verification_error("sentence JSONL must end with LF")
    records: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            _verification_error(f"invalid JSONL at line {line_number}: {exc}")
        if not isinstance(record, dict):
            _verification_error(f"JSONL line {line_number} must be an object")
        records.append(record)
    return records


def _publish_pair(
    output_path: Path,
    output_bytes: bytes,
    manifest_path: Path,
    manifest_bytes: bytes,
) -> None:
    output_temp: Path | None = None
    manifest_temp: Path | None = None
    output_published = False
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_temp = _write_temporary_sibling(output_path, output_bytes)
        manifest_temp = _write_temporary_sibling(manifest_path, manifest_bytes)
        output_temp.replace(output_path)
        output_published = True
        manifest_temp.replace(manifest_path)
    except OSError as exc:
        if output_published:
            _unlink_if_exists(output_path)
        _unlink_if_exists(manifest_path)
        raise YtcapError(
            ErrorCode.OUTPUT_WRITE_FAILED,
            f"could not publish sentence artifact pair '{output_path}': {exc}",
            exit_code=5,
        ) from exc
    finally:
        if output_temp is not None:
            _unlink_if_exists(output_temp)
        if manifest_temp is not None:
            _unlink_if_exists(manifest_temp)


def _write_temporary_sibling(destination: Path, payload: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        _unlink_if_exists(temporary_path)
        raise
    return temporary_path


def _serialize_manifest(manifest: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _ensure_destinations_absent(output_path: Path, manifest_path: Path) -> None:
    for path in (output_path, manifest_path):
        if path.exists():
            raise YtcapError(
                ErrorCode.OUTPUT_WRITE_FAILED,
                f"output file already exists '{path}'; remove it or choose another --out directory",
                exit_code=5,
            )


def _logical_source_filename(source_path: Path, output_dir: Path) -> str:
    if source_path.parent.name == "subtitles" and output_dir.name == "normalized":
        return f"../subtitles/{source_path.name}"
    return source_path.name


def _logical_metadata_filename(metadata_path: Path | None, output_dir: Path) -> str | None:
    if metadata_path is None:
        return None
    if metadata_path.parent.name == "videos" and output_dir.name == "normalized":
        return f"../videos/{metadata_path.name}"
    return metadata_path.name


def _resolve_artifact_path(manifest_path: Path, logical_filename: str) -> Path:
    bundle_root = manifest_path.parent.parent.resolve()
    candidate = (manifest_path.parent / logical_filename).resolve()
    try:
        candidate.relative_to(bundle_root)
    except ValueError:
        _verification_error("artifact filename escapes the bundle root")
    return candidate


def _required_mapping(data: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = data.get(field)
    if not isinstance(value, Mapping):
        _verification_error(f"manifest field {field} must be an object")
    return value


def _required_logical_filename(data: Mapping[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        _verification_error(f"manifest field {field} must be a logical/relative filename")
    return value


def _validate_identity(*, video_id: Any, language: Any, source: Any) -> None:
    if not isinstance(video_id, str) or not video_id:
        _verification_error("video_id must be a non-empty string")
    if not isinstance(language, str) or not language:
        _verification_error("language must be a non-empty string")
    if source not in KNOWN_SOURCES:
        _verification_error("source must be manual, auto, or unknown")


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"could not read {label} '{path}': {exc}",
            exit_code=2,
        ) from exc


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _verification_error(message: str) -> None:
    raise YtcapError(ErrorCode.PARSE_FAILED, message, exit_code=3)
