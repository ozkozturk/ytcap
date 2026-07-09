"""yt-dlp adapter tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.services.ytdlp_adapter import VideoSource, YtDlpAdapter  # noqa: E402


def supported_version_process() -> CompletedProcess[str]:
    return CompletedProcess(args=["yt-dlp", "--version"], returncode=0, stdout="2026.06.09\n", stderr="")


def with_supported_version(result: CompletedProcess[str]) -> list[CompletedProcess[str]]:
    return [supported_version_process(), result]


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
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")
        )

        result = YtDlpAdapter().extract_metadata(VideoSource(url="https://example.test/watch?v=abc123"))

        self.assertEqual(result, raw)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.Path.exists", return_value=True)
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_default_executable_prefers_sibling_over_path(
        self,
        _which: object,
        _exists: object,
        run: object,
    ) -> None:
        raw = {"id": "abc123", "title": "Example"}
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")
        )

        result = YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(result, raw)
        command = run.call_args.args[0]
        self.assertEqual(command[0], str(Path(sys.executable).with_name("yt-dlp")))
        self.assertNotEqual(command[0], "/usr/bin/yt-dlp")

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.importlib.metadata.version", return_value="2026.06.09")
    @patch("ytcap.services.ytdlp_adapter.Path.exists", return_value=False)
    @patch("ytcap.services.ytdlp_adapter.importlib.util.find_spec", return_value=object())
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_default_executable_prefers_installed_module_over_path(
        self,
        _which: object,
        _find_spec: object,
        _exists: object,
        _metadata_version: object,
        run: object,
    ) -> None:
        raw = {"id": "abc123", "title": "Example"}
        run.return_value = CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")

        result = YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(result, raw)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, "-m", "yt_dlp"])

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.importlib.metadata.version", return_value="2026.06.09")
    @patch("ytcap.services.ytdlp_adapter.Path.exists", return_value=False)
    @patch("ytcap.services.ytdlp_adapter.importlib.util.find_spec", return_value=object())
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value=None)
    def test_extract_metadata_can_use_installed_module(
        self,
        _which: object,
        _find_spec: object,
        _exists: object,
        _metadata_version: object,
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
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=1, stdout="", stderr="video unavailable")
        )

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(raised.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertEqual(raised.exception.message, "video unavailable")

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_invalid_json_returns_parse_error(self, _which: object, run: object) -> None:
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout="not json", stderr="")
        )

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_old_ytdlp_version_returns_controlled_error(self, _which: object, run: object) -> None:
        run.return_value = CompletedProcess(args=["yt-dlp", "--version"], returncode=0, stdout="2026.02.20\n", stderr="")

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_metadata(VideoSource(video_id="abc123"))

        self.assertEqual(raised.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertIn("below the supported minimum 2026.06.09", raised.exception.message)
        self.assertEqual(run.call_count, 1)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_download_subtitle_moves_generated_file(self, _which: object, run: object) -> None:
        def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if command[-1] == "--version":
                return supported_version_process()
            output_template = command[command.index("--output") + 1]
            temp_root = Path(output_template).parent
            (temp_root / "abc123.en.srt").write_text("subtitle text\n", encoding="utf-8")
            return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

        run.side_effect = fake_run

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "abc123.en.manual.srt"

            result = YtDlpAdapter().download_subtitle(
                VideoSource(video_id="abc123"),
                language="en",
                subtitle_source="manual",
                subtitle_format="srt",
                output_path=output_path,
            )

            self.assertEqual(result, output_path)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "subtitle text\n")

        command = run.call_args.args[0]
        self.assertIn("--write-subs", command)
        self.assertIn("--sub-langs", command)
        self.assertIn("--sub-format", command)
        self.assertEqual(command[-1], "https://www.youtube.com/watch?v=abc123")

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_download_subtitle_moves_english_variant_file_to_canonical_path(
        self,
        _which: object,
        run: object,
    ) -> None:
        def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if command[-1] == "--version":
                return supported_version_process()
            output_template = command[command.index("--output") + 1]
            temp_root = Path(output_template).parent
            (temp_root / "abc123.en-GB.srt").write_text("variant subtitle text\n", encoding="utf-8")
            return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

        run.side_effect = fake_run

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "abc123.en.manual.srt"

            result = YtDlpAdapter().download_subtitle(
                VideoSource(video_id="abc123"),
                language="en-GB",
                subtitle_source="manual",
                subtitle_format="srt",
                output_path=output_path,
            )

            self.assertEqual(result, output_path)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "variant subtitle text\n")

        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--sub-langs") + 1], "en-GB")

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_download_auto_subtitle_uses_auto_flag(self, _which: object, run: object) -> None:
        def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
            if command[-1] == "--version":
                return supported_version_process()
            output_template = command[command.index("--output") + 1]
            temp_root = Path(output_template).parent
            (temp_root / "abc123.en.vtt").write_text("WEBVTT\n", encoding="utf-8")
            return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

        run.side_effect = fake_run

        with tempfile.TemporaryDirectory() as temp_dir:
            YtDlpAdapter().download_subtitle(
                VideoSource(video_id="abc123"),
                language="en",
                subtitle_source="auto",
                subtitle_format="vtt",
                output_path=Path(temp_dir) / "abc123.en.auto.vtt",
            )

        self.assertIn("--write-auto-subs", run.call_args.args[0])

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_download_subtitle_missing_output_returns_controlled_error(self, _which: object, run: object) -> None:
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout="", stderr="")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(YtcapError) as raised:
                YtDlpAdapter().download_subtitle(
                    VideoSource(video_id="abc123"),
                    language="en",
                    subtitle_source="manual",
                    subtitle_format="srt",
                    output_path=Path(temp_dir) / "abc123.en.manual.srt",
                )

        self.assertEqual(raised.exception.code, ErrorCode.SUBTITLE_NOT_FOUND)
        self.assertEqual(raised.exception.exit_code, 4)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_extract_playlist_entries_returns_video_sources(self, _which: object, run: object) -> None:
        raw = {
            "id": "PLabc123",
            "title": "Test Playlist",
            "entries": [
                {"url": "abc12345678"},
                {"id": "xyz98765432", "url": "https://www.youtube.com/watch?v=xyz98765432"},
                {"id": "def55511122", "webpage_url": "https://www.youtube.com/watch?v=def55511122"},
                {"id": "ghi66633344"},
            ],
        }
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")
        )

        result = YtDlpAdapter().extract_playlist_entries(
            VideoSource(url="https://www.youtube.com/playlist?list=PLabc123")
        )

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].video_id, "abc12345678")
        self.assertIsNone(result[0].url)
        self.assertEqual(result[1].video_id, "xyz98765432")
        self.assertEqual(result[1].url, "https://www.youtube.com/watch?v=xyz98765432")
        self.assertEqual(result[2].video_id, "def55511122")
        self.assertEqual(result[2].url, "https://www.youtube.com/watch?v=def55511122")
        self.assertEqual(result[3].video_id, "ghi66633344")
        self.assertIsNone(result[3].url)

        command = run.call_args.args[0]
        self.assertIn("--flat-playlist", command)
        self.assertIn("--skip-download", command)
        self.assertIn("--dump-single-json", command)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_extract_playlist_empty_returns_empty_list(self, _which: object, run: object) -> None:
        raw = {"id": "PLempty", "entries": []}
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")
        )

        result = YtDlpAdapter().extract_playlist_entries(
            VideoSource(url="https://www.youtube.com/playlist?list=PLempty")
        )

        self.assertEqual(result, [])

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_extract_playlist_invalid_entries_returns_parse_error(self, _which: object, run: object) -> None:
        raw = {"id": "PLnoentries"}
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")
        )

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_playlist_entries(
                VideoSource(url="https://www.youtube.com/playlist?list=PLnoentries")
            )

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_extract_playlist_unusable_entries_return_parse_error(self, _which: object, run: object) -> None:
        raw = {"id": "PLbad", "entries": [{"title": "missing id and URL"}, "bad entry"]}
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=0, stdout=json.dumps(raw), stderr="")
        )

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_playlist_entries(
                VideoSource(url="https://www.youtube.com/playlist?list=PLbad")
            )

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)

    @patch("ytcap.services.ytdlp_adapter.subprocess.run")
    @patch("ytcap.services.ytdlp_adapter.shutil.which", return_value="/usr/bin/yt-dlp")
    def test_extract_playlist_failure_returns_controlled_error(self, _which: object, run: object) -> None:
        run.side_effect = with_supported_version(
            CompletedProcess(args=["yt-dlp"], returncode=1, stdout="", stderr="playlist not found")
        )

        with self.assertRaises(YtcapError) as raised:
            YtDlpAdapter().extract_playlist_entries(
                VideoSource(url="https://www.youtube.com/playlist?list=PLprivate")
            )

        self.assertEqual(raised.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertEqual(raised.exception.message, "playlist not found")


if __name__ == "__main__":
    unittest.main()
