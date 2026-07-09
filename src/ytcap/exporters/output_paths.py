"""Output directory and path helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ytcap.errors import ErrorCode, YtcapError


OUTPUT_DIRECTORIES = ("videos", "subtitles", "normalized", "runs", "failed")
SAFE_FILENAME_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class OutputLayout:
    root: Path

    @property
    def videos_dir(self) -> Path:
        return self.root / "videos"

    @property
    def subtitles_dir(self) -> Path:
        return self.root / "subtitles"

    @property
    def normalized_dir(self) -> Path:
        return self.root / "normalized"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    @property
    def failed_dir(self) -> Path:
        return self.root / "failed"

    def metadata_path(self, video_id: str) -> Path:
        return self.videos_dir / f"{safe_filename_part(video_id, field_name='video_id')}.info.json"

    def subtitle_path(self, video_id: str, language: str, source: str, subtitle_format: str) -> Path:
        filename = ".".join(
            [
                safe_filename_part(video_id, field_name="video_id"),
                safe_filename_part(language, field_name="language"),
                safe_filename_part(source, field_name="source"),
                safe_filename_part(subtitle_format, field_name="format"),
            ]
        )
        return self.subtitles_dir / filename

    def normalized_path(self, video_id: str, language: str, segments: str) -> Path:
        return normalized_file_path(self.normalized_dir, video_id=video_id, language=language, segments=segments)

    def run_manifest_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{safe_filename_part(run_id, field_name='run_id')}.manifest.json"

    def failed_path(self) -> Path:
        return self.failed_dir / "failed.jsonl"


def build_output_layout(root: str | Path) -> OutputLayout:
    return OutputLayout(root=Path(root))


def infer_export_output_layout(input_path: str | Path, output_dir: str | Path) -> OutputLayout:
    source_path = Path(input_path)
    normalized_dir = Path(output_dir)

    if source_path.parent.name == "subtitles":
        return build_output_layout(source_path.parent.parent)
    if source_path.name == "subtitles":
        return build_output_layout(source_path.parent)
    if normalized_dir.name == "normalized":
        return build_output_layout(normalized_dir.parent)

    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        (
            "could not infer standard output layout for metadata; "
            "use subtitle input under a 'subtitles' directory or set --out to a 'normalized' directory"
        ),
        exit_code=2,
    )


def normalized_file_path(root: str | Path, *, video_id: str, language: str, segments: str) -> Path:
    filename = ".".join(
        [
            safe_filename_part(video_id, field_name="video_id"),
            safe_filename_part(language, field_name="language"),
            safe_filename_part(segments, field_name="segments"),
            "jsonl",
        ]
    )
    return Path(root) / filename


def safe_filename_part(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise YtcapError(
            ErrorCode.INVALID_INPUT,
            f"{field_name} must be a string safe for file names",
            exit_code=2,
        )
    if not value or value in {".", ".."}:
        _raise_unsafe_filename_part(value, field_name=field_name)
    if Path(value).is_absolute() or "/" in value or "\\" in value:
        _raise_unsafe_filename_part(value, field_name=field_name)
    if any(ord(character) < 32 for character in value):
        _raise_unsafe_filename_part(value, field_name=field_name)
    if SAFE_FILENAME_PART_RE.fullmatch(value) is None:
        _raise_unsafe_filename_part(value, field_name=field_name)
    return value


def _raise_unsafe_filename_part(value: str, *, field_name: str) -> None:
    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        f"{field_name} contains unsafe filename characters: {value!r}",
        exit_code=2,
    )


def ensure_output_layout(root: str | Path) -> OutputLayout:
    layout = build_output_layout(root)
    try:
        for directory_name in OUTPUT_DIRECTORIES:
            (layout.root / directory_name).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise YtcapError(
            ErrorCode.OUTPUT_WRITE_FAILED,
            f"could not create output directory '{layout.root}': {exc}",
            exit_code=5,
        ) from exc
    return layout
