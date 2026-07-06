"""Batch input parser service."""

from __future__ import annotations

from pathlib import Path

from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.ytdlp_adapter import VideoSource


def parse_batch_content(content: str) -> list[VideoSource]:
    """Parse batch file content containing video URLs or IDs line-by-line.

    Supports comments (lines starting with # or inline #) and ignores empty lines.
    """
    sources: list[VideoSource] = []
    for line in content.splitlines():
        if "#" in line:
            line = line.split("#", 1)[0]
        
        stripped = line.strip()
        if not stripped:
            continue
        
        # Simple heuristic to distinguish URLs from IDs
        if "://" in stripped or "/" in stripped or stripped.startswith("http"):
            sources.append(VideoSource(url=stripped))
        else:
            sources.append(VideoSource(video_id=stripped))
            
    return sources


def parse_batch_file(path: str | Path) -> list[VideoSource]:
    """Read a batch file and parse its content.

    Raises YtcapError with INVALID_INPUT code if the file cannot be read.
    """
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"could not read batch file '{path}': {exc}",
            exit_code=2,
        ) from exc
    return parse_batch_content(content)
