"""CLI tests."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap import __version__  # noqa: E402
from ytcap.cli import build_parser, main  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def sample_raw_metadata() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "sample.info.json").read_text(encoding="utf-8"))


class CliTest(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(argv)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_help_mentions_program_name(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(io.StringIO()) as stdout:
            parser.parse_args(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("ytcap", stdout.getvalue())
        self.assertIn("inspect", stdout.getvalue())
        self.assertIn("video", stdout.getvalue())
        self.assertIn("export", stdout.getvalue())
        self.assertIn("batch", stdout.getvalue())

    def test_version_outputs_package_version(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(io.StringIO()) as stdout:
            parser.parse_args(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"ytcap {__version__}")

    def test_conflicting_logging_flags_return_user_error(self) -> None:
        exit_code, _, stderr = self.run_cli(["--verbose", "--quiet"])

        self.assertEqual(exit_code, 2)
        self.assertIn("error: --verbose and --quiet cannot be used together", stderr)
        self.assertIn("code: CONFLICTING_FLAGS", stderr)

    def test_successful_empty_invocation_returns_zero(self) -> None:
        self.assertEqual(main([]), 0)

    @patch("ytcap.commands.inspect.YtDlpAdapter")
    def test_inspect_command_accepts_url(self, adapter_class: object) -> None:
        adapter_class.return_value.extract_metadata.return_value = sample_raw_metadata()

        exit_code, stdout, stderr = self.run_cli(["inspect", "--url", "https://www.youtube.com/watch?v=abc123"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Video", stdout)
        self.assertIn("ID: abc123", stdout)
        self.assertIn("Title: Example Video", stdout)
        self.assertIn("en: auto, manual", stdout)
        self.assertIn("tr: auto", stdout)

    @patch("ytcap.commands.inspect.YtDlpAdapter")
    def test_inspect_json_outputs_summary_payload(self, adapter_class: object) -> None:
        adapter_class.return_value.extract_metadata.return_value = sample_raw_metadata()

        exit_code, stdout, stderr = self.run_cli(["inspect", "--id", "abc123", "--json"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(payload["video_id"], "abc123")
        self.assertEqual(payload["title"], "Example Video")

    @patch("ytcap.commands.inspect.YtDlpAdapter")
    def test_inspect_list_subs_outputs_format_details(self, adapter_class: object) -> None:
        adapter_class.return_value.extract_metadata.return_value = sample_raw_metadata()

        exit_code, stdout, stderr = self.run_cli(["inspect", "--id", "abc123", "--list-subs"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("en manual: srt, vtt", stdout)
        self.assertIn("en auto: vtt", stdout)
        self.assertIn("tr auto: vtt", stdout)

    def test_inspect_rejects_conflicting_video_sources(self) -> None:
        exit_code, _, stderr = self.run_cli(["inspect", "--url", "https://example.test", "--id", "abc123"])

        self.assertEqual(exit_code, 2)
        self.assertIn("code: CONFLICTING_FLAGS", stderr)

    def test_inspect_requires_video_source(self) -> None:
        exit_code, _, stderr = self.run_cli(["inspect"])

        self.assertEqual(exit_code, 2)
        self.assertIn("code: INVALID_INPUT", stderr)

    def test_video_command_accepts_core_options(self) -> None:
        exit_code, stdout, stderr = self.run_cli(
            [
                "video",
                "--id",
                "abc123",
                "--lang",
                "tr",
                "--source",
                "manual",
                "--format",
                "vtt",
                "--out",
                "./out",
                "--dry-run",
            ]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Video command parsed.", stdout)
        self.assertIn("id=abc123", stdout)
        self.assertIn("Language: tr", stdout)
        self.assertIn("Dry run: no files written.", stdout)

    def test_video_rejects_skip_existing_with_overwrite(self) -> None:
        exit_code, _, stderr = self.run_cli(["video", "--id", "abc123", "--skip-existing", "--overwrite"])

        self.assertEqual(exit_code, 2)
        self.assertIn("code: CONFLICTING_FLAGS", stderr)

    def test_video_rejects_metadata_only_with_subs_only(self) -> None:
        exit_code, _, stderr = self.run_cli(["video", "--id", "abc123", "--metadata-only", "--subs-only"])

        self.assertEqual(exit_code, 2)
        self.assertIn("code: CONFLICTING_FLAGS", stderr)

    def test_export_command_accepts_core_options(self) -> None:
        exit_code, stdout, stderr = self.run_cli(
            ["export", "--input", "./data/subtitles", "--segments", "sentence", "--format", "jsonl"]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Export command parsed.", stdout)
        self.assertIn("Segments: sentence", stdout)

    def test_export_requires_input(self) -> None:
        stderr = io.StringIO()

        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(stderr):
            main(["export"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("the following arguments are required: --input", stderr.getvalue())

    def test_batch_placeholder_returns_clear_error(self) -> None:
        exit_code, _, stderr = self.run_cli(["batch", "--input", "videos.txt"])

        self.assertEqual(exit_code, 1)
        self.assertIn("batch command is not implemented yet", stderr)
        self.assertIn("code: NOT_IMPLEMENTED", stderr)


if __name__ == "__main__":
    unittest.main()
