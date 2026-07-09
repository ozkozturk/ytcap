"""Read normalized metadata JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ytcap.errors import ErrorCode, YtcapError


def read_metadata_json(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"metadata file not found '{metadata_path}'",
            exit_code=2,
        ) from exc
    except OSError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"could not read metadata file '{metadata_path}': {exc}",
            exit_code=2,
        ) from exc
    except json.JSONDecodeError as exc:
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"could not parse metadata JSON '{metadata_path}': {exc}",
            exit_code=3,
        ) from exc

    if not isinstance(payload, dict):
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"metadata JSON must be an object '{metadata_path}'",
            exit_code=3,
        )
    return payload
