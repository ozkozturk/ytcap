"""yt-dlp subprocess adapter."""

from __future__ import annotations

import json
import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ytcap.errors import ErrorCode, YtcapError


@dataclass(frozen=True)
class VideoSource:
    url: str | None = None
    video_id: str | None = None

    def target(self) -> str:
        if self.url:
            return self.url
        if self.video_id:
            return f"https://www.youtube.com/watch?v={self.video_id}"
        raise YtcapError(ErrorCode.INVALID_INPUT, "one of --url or --id is required", exit_code=2)


class YtDlpAdapter:
    def __init__(self, executable: str = "yt-dlp") -> None:
        self.executable = executable

    def is_available(self) -> bool:
        return self._command_prefix() is not None

    def extract_metadata(self, source: VideoSource) -> dict[str, Any]:
        command_prefix = self._command_prefix()
        if command_prefix is None:
            raise YtcapError(
                ErrorCode.YTDLP_NOT_AVAILABLE,
                "yt-dlp executable was not found",
                exit_code=3,
            )

        command = [
            *command_prefix,
            "--dump-single-json",
            "--skip-download",
            "--no-warnings",
            source.target(),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise YtcapError(
                ErrorCode.YTDLP_NOT_AVAILABLE,
                "yt-dlp executable was not found",
                exit_code=3,
            ) from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or "yt-dlp failed to extract metadata"
            raise YtcapError(ErrorCode.YTDLP_FAILED, message, exit_code=3)

        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise YtcapError(
                ErrorCode.PARSE_FAILED,
                "yt-dlp returned invalid JSON",
                exit_code=3,
            ) from exc

        if not isinstance(raw, dict):
            raise YtcapError(ErrorCode.PARSE_FAILED, "yt-dlp returned unexpected metadata", exit_code=3)
        return raw

    def _command_prefix(self) -> list[str] | None:
        executable_path = shutil.which(self.executable)
        if executable_path:
            return [executable_path]

        sibling_executable = Path(sys.executable).with_name(self.executable)
        if sibling_executable.exists():
            return [str(sibling_executable)]

        if self.executable == "yt-dlp" and importlib.util.find_spec("yt_dlp") is not None:
            return [sys.executable, "-m", "yt_dlp"]

        return None
