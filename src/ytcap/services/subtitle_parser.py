"""Subtitle parsing helpers."""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

from ytcap.errors import ErrorCode, YtcapError
from ytcap.models.subtitle import SubtitleCue


SRT_TIMESTAMP_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$"
)
VTT_TIMESTAMP_RE = re.compile(
    r"^(?P<start>(?:\d{2}:)?\d{2}:\d{2}[,.]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2}:)?\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$"
)
VTT_NON_CUE_PREFIXES = ("NOTE", "STYLE", "REGION")


def parse_srt_file(path: str | Path) -> list[SubtitleCue]:
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"could not read SRT file '{path}': {exc}",
            exit_code=3,
        ) from exc
    return parse_srt_text(text)


def parse_srt_text(text: str) -> list[SubtitleCue]:
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized_text:
        return []

    raw_blocks = _split_subtitle_blocks(normalized_text)
    merged_blocks: list[str] = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.split("\n")]
        is_new_block = False
        if len(lines) >= 2:
            if SRT_TIMESTAMP_RE.match(lines[1]):
                is_new_block = True

        if is_new_block or not merged_blocks:
            merged_blocks.append(block)
        else:
            merged_blocks[-1] = merged_blocks[-1] + "\n\n" + block

    cues: list[SubtitleCue] = []
    for block_number, block in enumerate(merged_blocks, start=1):
        cues.append(_parse_srt_block(block, block_number=block_number))
    return cues


def parse_vtt_file(path: str | Path) -> list[SubtitleCue]:
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise YtcapError(
            ErrorCode.PARSE_FAILED,
            f"could not read VTT file '{path}': {exc}",
            exit_code=3,
        ) from exc
    return parse_vtt_text(text)


def parse_vtt_text(text: str) -> list[SubtitleCue]:
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized_text:
        return []

    cue_text = _strip_vtt_header(normalized_text)
    if not cue_text:
        return []

    raw_blocks = _split_subtitle_blocks(cue_text)
    merged_blocks: list[str] = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.split("\n")]
        is_new_block = False
        if len(lines) >= 1:
            first_line = lines[0]
            if any(first_line == prefix or first_line.startswith(f"{prefix} ") for prefix in VTT_NON_CUE_PREFIXES):
                is_new_block = True
            elif VTT_TIMESTAMP_RE.match(first_line):
                is_new_block = True
            elif len(lines) >= 2 and VTT_TIMESTAMP_RE.match(lines[1]):
                is_new_block = True

        if is_new_block or not merged_blocks:
            merged_blocks.append(block)
        else:
            merged_blocks[-1] = merged_blocks[-1] + "\n\n" + block

    cues: list[SubtitleCue] = []
    for block_number, block in enumerate(merged_blocks, start=1):
        if _is_vtt_non_cue_block(block):
            continue
        cues.append(_parse_vtt_block(block, block_number=block_number))
    return cues


def _split_subtitle_blocks(text: str) -> list[str]:
    return [block for block in re.split(r"\n(?:[ \t]*\n)+", text) if block.strip()]


def _parse_srt_block(block: str, *, block_number: int) -> SubtitleCue:
    lines = [line.strip() for line in block.split("\n")]
    if len(lines) < 2:
        _raise_malformed(block_number, "expected index and timestamp lines")

    index_line = lines[0]
    if not index_line.isdigit():
        _raise_malformed(block_number, "expected numeric index")
    index = int(index_line)

    timestamp_match = SRT_TIMESTAMP_RE.match(lines[1])
    if timestamp_match is None:
        _raise_malformed(block_number, "expected SRT timestamp range")

    start = _timestamp_to_seconds(timestamp_match.group("start"))
    end = _timestamp_to_seconds(timestamp_match.group("end"))
    if end < start:
        _raise_malformed(block_number, "end timestamp cannot be before start timestamp")

    text = _clean_cue_text(lines[2:])
    return SubtitleCue(index=index, start=start, end=end, text=text)


def _strip_vtt_header(text: str) -> str:
    lines = text.split("\n")
    if not lines or not lines[0].startswith("WEBVTT"):
        _raise_malformed_vtt(1, "expected WEBVTT header")

    for index, line in enumerate(lines[1:], start=1):
        if not line.strip():
            return "\n".join(lines[index + 1 :]).strip()
    return ""


def _is_vtt_non_cue_block(block: str) -> bool:
    first_line = block.split("\n", maxsplit=1)[0].strip()
    return any(first_line == prefix or first_line.startswith(f"{prefix} ") for prefix in VTT_NON_CUE_PREFIXES)


def _parse_vtt_block(block: str, *, block_number: int) -> SubtitleCue:
    lines = [line.strip() for line in block.split("\n")]
    if len(lines) < 1:
        _raise_malformed_vtt(block_number, "expected timestamp line")

    timestamp_line_index = 0
    timestamp_match = VTT_TIMESTAMP_RE.match(lines[0])
    cue_index: int | None = None
    if timestamp_match is None:
        if len(lines) < 2:
            _raise_malformed_vtt(block_number, "expected cue identifier and timestamp lines")
        cue_index = int(lines[0]) if lines[0].isdigit() else None
        timestamp_line_index = 1
        timestamp_match = VTT_TIMESTAMP_RE.match(lines[1])
        if timestamp_match is None:
            _raise_malformed_vtt(block_number, "expected VTT timestamp range")

    start = _timestamp_to_seconds(timestamp_match.group("start"))
    end = _timestamp_to_seconds(timestamp_match.group("end"))
    if end < start:
        _raise_malformed_vtt(block_number, "end timestamp cannot be before start timestamp")

    text = _clean_cue_text(lines[timestamp_line_index + 1 :])
    return SubtitleCue(index=cue_index, start=start, end=end, text=text)


def _clean_cue_text(lines: list[str]) -> str:
    cleaned_lines: list[str] = []
    for line in lines:
        cleaned = unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if cleaned:
            cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)


def _timestamp_to_seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 3:
        hours_text, minutes_text, rest = parts
    else:
        hours_text = "0"
        minutes_text, rest = parts
    seconds_text, milliseconds_text = rest.split(".")
    return (
        int(hours_text) * 3600
        + int(minutes_text) * 60
        + int(seconds_text)
        + int(milliseconds_text) / 1000
    )


def _raise_malformed(block_number: int, reason: str) -> None:
    raise YtcapError(
        ErrorCode.PARSE_FAILED,
        f"malformed SRT block {block_number}: {reason}",
        exit_code=3,
    )


def _raise_malformed_vtt(block_number: int, reason: str) -> None:
    raise YtcapError(
        ErrorCode.PARSE_FAILED,
        f"malformed VTT block {block_number}: {reason}",
        exit_code=3,
    )
