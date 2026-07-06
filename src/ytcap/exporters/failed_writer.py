"""Failed JSONL writer helper."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ytcap.errors import ErrorCode, YtcapError


def append_failed_record(
    path: str | Path,
    *,
    video_id: str | None,
    url: str | None,
    code: str,
    message: str,
) -> None:
    """Append a failure record to the failed JSONL file."""
    output_path = Path(path)
    record = {
        "schema_version": "0.1",
        "video_id": video_id,
        "url": url,
        "code": code,
        "message": message,
        "failed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError as exc:
        raise YtcapError(
            ErrorCode.OUTPUT_WRITE_FAILED,
            f"could not write failed record to '{output_path}': {exc}",
            exit_code=5,
        ) from exc
