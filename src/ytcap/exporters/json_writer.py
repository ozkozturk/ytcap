"""JSON file writing helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ytcap.errors import ErrorCode, YtcapError


def write_json_file(
    path: str | Path,
    data: dict[str, Any],
    *,
    skip_existing: bool = False,
    overwrite: bool = False,
) -> bool:
    """Write a JSON document and return whether the file was written."""

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

    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    except OSError as exc:
        raise YtcapError(
            ErrorCode.OUTPUT_WRITE_FAILED,
            f"could not write JSON file '{output_path}': {exc}",
            exit_code=5,
        ) from exc
    return True
