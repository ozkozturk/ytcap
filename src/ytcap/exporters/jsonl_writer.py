"""JSONL file writing helpers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ytcap.errors import ErrorCode, YtcapError
from ytcap.models.subtitle import SubtitleCue


SCHEMA_VERSION = "0.1"


def cue_jsonl_record(
    cue: SubtitleCue,
    *,
    video_id: str,
    language: str,
    source: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "type": "cue",
        "video_id": video_id,
        "language": language,
        "source": source,
        "start": cue.start,
        "end": cue.end,
        "text": cue.text,
        "cue_index": cue.index,
    }


def write_cue_jsonl_file(
    path: str | Path,
    cues: Sequence[SubtitleCue],
    *,
    video_id: str,
    language: str,
    source: str,
    skip_existing: bool = False,
    overwrite: bool = False,
) -> bool:
    output_path = Path(path)
    if output_path.exists():
        if skip_existing:
            return False
        if not overwrite:
            raise YtcapError(
                ErrorCode.OUTPUT_WRITE_FAILED,
                f"output file already exists '{output_path}'; use --overwrite or --skip-existing",
                exit_code=5,
            )

    records = [
        cue_jsonl_record(cue, video_id=video_id, language=language, source=source)
        for cue in cues
    ]
    payload = "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(payload, encoding="utf-8")
        temporary_path.replace(output_path)
    except OSError as exc:
        raise YtcapError(
            ErrorCode.OUTPUT_WRITE_FAILED,
            f"could not write JSONL file '{output_path}': {exc}",
            exit_code=5,
        ) from exc
    return True
