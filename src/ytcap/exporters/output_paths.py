"""Output directory and path helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ytcap.errors import ErrorCode, YtcapError


OUTPUT_DIRECTORIES = ("videos", "subtitles", "normalized", "runs", "failed")


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
        return self.videos_dir / f"{video_id}.info.json"

    def subtitle_path(self, video_id: str, language: str, source: str, subtitle_format: str) -> Path:
        return self.subtitles_dir / f"{video_id}.{language}.{source}.{subtitle_format}"

    def normalized_path(self, video_id: str, language: str, segments: str) -> Path:
        return self.normalized_dir / f"{video_id}.{language}.{segments}.jsonl"

    def run_manifest_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.manifest.json"

    def failed_path(self) -> Path:
        return self.failed_dir / "failed.jsonl"


def build_output_layout(root: str | Path) -> OutputLayout:
    return OutputLayout(root=Path(root))


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
