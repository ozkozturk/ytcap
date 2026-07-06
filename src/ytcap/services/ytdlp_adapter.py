"""yt-dlp subprocess adapter."""

from __future__ import annotations

import json
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
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
        command_prefix = self._require_command_prefix()

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

    def extract_playlist_entries(self, source: VideoSource) -> list[VideoSource]:
        command_prefix = self._require_command_prefix()

        command = [
            *command_prefix,
            "--flat-playlist",
            "--skip-download",
            "--dump-single-json",
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
            message = completed.stderr.strip() or "yt-dlp failed to extract playlist entries"
            raise YtcapError(ErrorCode.YTDLP_FAILED, message, exit_code=3)

        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise YtcapError(
                ErrorCode.PARSE_FAILED,
                "yt-dlp returned invalid playlist JSON",
                exit_code=3,
            ) from exc

        if not isinstance(data, dict):
            raise YtcapError(ErrorCode.PARSE_FAILED, "yt-dlp returned unexpected playlist data", exit_code=3)

        entries = data.get("entries")
        if not isinstance(entries, list):
            raise YtcapError(ErrorCode.PARSE_FAILED, "yt-dlp returned unexpected playlist entries", exit_code=3)

        sources: list[VideoSource] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source_entry = _playlist_entry_source(entry)
            if source_entry is not None:
                sources.append(source_entry)
        if entries and not sources:
            raise YtcapError(
                ErrorCode.PARSE_FAILED,
                "yt-dlp playlist JSON did not contain usable video entries",
                exit_code=3,
            )
        return sources

    def download_subtitle(
        self,
        source: VideoSource,
        *,
        language: str,
        subtitle_source: str,
        subtitle_format: str,
        output_path: str | Path,
    ) -> Path:
        command_prefix = self._require_command_prefix()
        write_flag = _subtitle_write_flag(subtitle_source)
        destination = Path(output_path)

        with tempfile.TemporaryDirectory(prefix="ytcap-subtitle-") as temp_dir:
            temp_root = Path(temp_dir)
            command = [
                *command_prefix,
                "--skip-download",
                "--no-warnings",
                "--no-playlist",
                write_flag,
                "--sub-langs",
                language,
                "--sub-format",
                subtitle_format,
                "--output",
                str(temp_root / "%(id)s"),
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
                message = completed.stderr.strip() or "yt-dlp failed to download subtitles"
                raise YtcapError(ErrorCode.YTDLP_FAILED, message, exit_code=3)

            subtitle_file = _find_downloaded_subtitle(temp_root, language=language, subtitle_format=subtitle_format)
            if subtitle_file is None:
                raise YtcapError(
                    ErrorCode.SUBTITLE_NOT_FOUND,
                    f"yt-dlp did not create subtitle file for language '{language}' and format '{subtitle_format}'",
                    exit_code=4,
                )

            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                subtitle_file.replace(destination)
            except OSError as exc:
                raise YtcapError(
                    ErrorCode.OUTPUT_WRITE_FAILED,
                    f"could not write subtitle file '{destination}': {exc}",
                    exit_code=5,
                ) from exc

        return destination

    def _require_command_prefix(self) -> list[str]:
        command_prefix = self._command_prefix()
        if command_prefix is None:
            raise YtcapError(
                ErrorCode.YTDLP_NOT_AVAILABLE,
                "yt-dlp executable was not found",
                exit_code=3,
            )
        return command_prefix

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


def _subtitle_write_flag(subtitle_source: str) -> str:
    if subtitle_source == "manual":
        return "--write-subs"
    if subtitle_source == "auto":
        return "--write-auto-subs"
    raise YtcapError(
        ErrorCode.INVALID_INPUT,
        f"unsupported subtitle source '{subtitle_source}'",
        exit_code=2,
    )


def _playlist_entry_source(entry: dict[str, Any]) -> VideoSource | None:
    entry_id = _clean_string(entry.get("id"))
    webpage_url = _clean_string(entry.get("webpage_url"))
    if webpage_url and _is_http_url(webpage_url):
        return VideoSource(url=webpage_url, video_id=entry_id)

    entry_url = _clean_string(entry.get("url"))
    if entry_url and _is_http_url(entry_url):
        return VideoSource(url=entry_url, video_id=entry_id)
    if entry_url and _looks_like_youtube_video_id(entry_url):
        return VideoSource(video_id=entry_url)
    if entry_id:
        return VideoSource(video_id=entry_id)
    return None


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _looks_like_youtube_video_id(value: str) -> bool:
    return re.fullmatch(r"[a-zA-Z0-9_-]{11}", value) is not None


def _find_downloaded_subtitle(temp_root: Path, *, language: str, subtitle_format: str) -> Path | None:
    expected_suffix = f".{language}.{subtitle_format}"
    exact_matches = sorted(
        path for path in temp_root.iterdir() if path.is_file() and path.name.endswith(expected_suffix)
    )
    if exact_matches:
        return exact_matches[0]

    format_matches = sorted(
        path for path in temp_root.iterdir() if path.is_file() and path.suffix == f".{subtitle_format}"
    )
    if len(format_matches) == 1:
        return format_matches[0]
    return None
