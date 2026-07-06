"""yt-dlp adapter tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.services.ytdlp_adapter import VideoSource, YtDlpAdapter  # noqa: E402


class YtDlpAdapterTest(unittest.TestCase):
    def test_video_id_source_builds_watch_url(self) -> None:
        self.assertEqual(VideoSource(video_id="abc123").target(), "https://www.youtube.com/watch?v=abc123")

    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value=None)
    def test_missing_ytdlp_returns_controlled_error(self, _which: object) -> None:
        adapter = YtDlpAdapter(executable="missing-yt-dlp")

        with self.assertRaises(YtcapError) as raised:
            adapter.extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(raised.exception.code, ErrorCode.YTDLP_NOT_AVAILABLE)
        self.assertEqual(raised.exception.exit_code, 3)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_extract_metadata_returns_raw_json(self, _which: object, run: object) -> None:
        raw = {"id": "abc123", "title": "Example"}
        run.return_value = CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")

        result = YtDlpAdapter().extract_metadata(VideoSource(url="https://example.test/watch?v=abc123"))

        self.assertEqual(result, raw)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.Path.exists", return_value=False)
    @patch("ytcap.services.ytdlp_adapter.importlib.util.find_spec", return_value=object())
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value=None)
    def test_extract_metadata_can_use_installed_module(
        self,
        _which: object,
        _find_spec: object,
        _exists: object,
        run: object,
    ) -> None:
        raw = {"id": "abc123", "title": "Example"}
        run.return_value = CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")

        result = YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(result, raw)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, "-m", "yt_dlp"])

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_ytdlp_failure_returns_controlled_error(self, _which: object, run: object) -> None:
        run.return_value = CompletedProcess(args=["yt-dlp"], returncode=1, stdout="", stderr="video unavailable")

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(raised.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertEqual(raised.exception.message, "video unavailable")

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_invalid_json_returns_parse_error(self, _which: object, run: object) -> None:
        run.return_value = CompletedProcess(args=["yt-dlp"], returncode=0, stdout="not json", stderr="")

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)


if __name__ == "__main__":
    unittest.main()
