"""CLI tests."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap import __version__  # noqa: E402
from ytcap.cli import build_parser, main  # noqa: E402
from ytcap.exporters.output_paths import OUTPUT_DIRECTORIES  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def sample_raw_metadata() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "sample.info.json").read_text(encoding="utf-8"))


def configure_fake_video_adapter(adapter_class: object) -> object:
    adapter = adapter_class.return_value
    adapter.extract_metadata.return_value = sample_raw_metadata()

    def download_subtitle(
        _source: object,
        *,
        language: str,
        subtitle_source: str,
        subtitle_format: str,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"subtitle {language} {subtitle_source} {subtitle_format}\n",
            encoding="utf-8",
        )
        return path

    adapter.download_subtitle.side_effect = download_subtitle
    return adapter


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

    def test_video_rejects_unsupported_subtitle_format(self) -> None:
        exit_code, _, stderr = self.run_cli(["video", "--id", "abc123", "--format", "json"])

        self.assertEqual(exit_code, 2)
        self.assertIn("unsupported subtitle format 'json'", stderr)
        self.assertIn("code: UNSUPPORTED_FORMAT", stderr)

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_command_prepares_output_directories(self, adapter_class: object) -> None:
        configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"

            exit_code, stdout, stderr = self.run_cli(["video", "--id", "abc123", "--out", str(output_dir)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Output directories prepared.", stdout)
            for directory_name in OUTPUT_DIRECTORIES:
                self.assertTrue((output_dir / directory_name).is_dir())

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_command_writes_metadata_and_subtitle(self, adapter_class: object) -> None:
        adapter = configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"

            exit_code, stdout, stderr = self.run_cli(["video", "--id", "abc123", "--out", str(output_dir)])

            metadata_path = output_dir / "videos" / "abc123.info.json"
            subtitle_path = output_dir / "subtitles" / "abc123.en.manual.srt"
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn(f"Metadata written: {metadata_path}", stdout)
            self.assertIn(f"Subtitle written: {subtitle_path}", stdout)
            self.assertTrue(metadata_path.is_file())
            self.assertEqual(subtitle_path.read_text(encoding="utf-8"), "subtitle en manual srt\n")

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            tracks = {(item["language"], item["source"]): item for item in metadata["subtitles"]}
            self.assertTrue(tracks[("en", "manual")]["selected"])
            self.assertTrue(tracks[("en", "manual")]["downloaded"])
            self.assertEqual(tracks[("en", "manual")]["path"], str(subtitle_path))
            adapter.download_subtitle.assert_called_once()

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_metadata_only_writes_no_subtitle(self, adapter_class: object) -> None:
        adapter = configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"

            exit_code, stdout, stderr = self.run_cli(
                ["video", "--id", "abc123", "--out", str(output_dir), "--metadata-only"]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Metadata written:", stdout)
            self.assertTrue((output_dir / "videos" / "abc123.info.json").is_file())
            self.assertFalse((output_dir / "subtitles" / "abc123.en.manual.srt").exists())
            adapter.download_subtitle.assert_not_called()

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_missing_subtitle_returns_controlled_error_after_metadata(self, adapter_class: object) -> None:
        adapter = configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"

            exit_code, _, stderr = self.run_cli(["video", "--id", "abc123", "--lang", "de", "--out", str(output_dir)])

            self.assertEqual(exit_code, 4)
            self.assertIn("code: SUBTITLE_NOT_FOUND", stderr)
            self.assertTrue((output_dir / "videos" / "abc123.info.json").is_file())
            adapter.download_subtitle.assert_not_called()

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_existing_output_requires_overwrite_or_skip_existing(self, adapter_class: object) -> None:
        adapter = configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"
            metadata_path = output_dir / "videos" / "abc123.info.json"
            metadata_path.parent.mkdir(parents=True)
            metadata_path.write_text("{}\n", encoding="utf-8")

            exit_code, _, stderr = self.run_cli(["video", "--id", "abc123", "--out", str(output_dir)])

            self.assertEqual(exit_code, 5)
            self.assertIn("use --overwrite or --skip-existing", stderr)
            self.assertIn("code: OUTPUT_WRITE_FAILED", stderr)
            adapter.download_subtitle.assert_not_called()

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_overwrite_replaces_existing_outputs(self, adapter_class: object) -> None:
        configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"
            metadata_path = output_dir / "videos" / "abc123.info.json"
            subtitle_path = output_dir / "subtitles" / "abc123.en.manual.srt"
            metadata_path.parent.mkdir(parents=True)
            subtitle_path.parent.mkdir(parents=True)
            metadata_path.write_text("{}\n", encoding="utf-8")
            subtitle_path.write_text("old subtitle\n", encoding="utf-8")

            exit_code, _, stderr = self.run_cli(
                ["video", "--id", "abc123", "--out", str(output_dir), "--overwrite"]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertEqual(subtitle_path.read_text(encoding="utf-8"), "subtitle en manual srt\n")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["video"]["title"], "Example Video")

    @patch("ytcap.commands.video.YtDlpAdapter")
    def test_video_skip_existing_leaves_existing_outputs(self, adapter_class: object) -> None:
        adapter = configure_fake_video_adapter(adapter_class)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "data"
            metadata_path = output_dir / "videos" / "abc123.info.json"
            subtitle_path = output_dir / "subtitles" / "abc123.en.manual.srt"
            metadata_path.parent.mkdir(parents=True)
            subtitle_path.parent.mkdir(parents=True)
            metadata_path.write_text("{}\n", encoding="utf-8")
            subtitle_path.write_text("old subtitle\n", encoding="utf-8")

            exit_code, stdout, stderr = self.run_cli(
                ["video", "--id", "abc123", "--out", str(output_dir), "--skip-existing"]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn(f"Metadata skipped: {metadata_path}", stdout)
            self.assertIn(f"Subtitle skipped: {subtitle_path}", stdout)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), "{}\n")
            self.assertEqual(subtitle_path.read_text(encoding="utf-8"), "old subtitle\n")
            adapter.download_subtitle.assert_not_called()

    def test_export_command_writes_jsonl_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "abc123.en.manual.srt"
            output_dir = root / "normalized"
            subtitle_text = (FIXTURE_DIR / "sample.en.srt").read_text(encoding="utf-8")
            subtitle_path.write_text(subtitle_text, encoding="utf-8")

            exit_code, stdout, stderr = self.run_cli(
                [
                    "export",
                    "--input",
                    str(subtitle_path),
                    "--segments",
                    "cue",
                    "--format",
                    "jsonl",
                    "--out",
                    str(output_dir),
                ]
            )

            output_path = output_dir / "abc123.en.cue.jsonl"
            records = [
                json.loads(line)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Export complete.", stdout)
            self.assertIn("Files exported: 1", stdout)
            self.assertTrue(output_path.is_file())
            self.assertEqual(records[0]["type"], "cue")
            self.assertEqual(records[0]["video_id"], "abc123")
            self.assertEqual(records[0]["language"], "en")
            self.assertEqual(records[0]["source"], "manual")

    def test_export_requires_input(self) -> None:
        stderr = io.StringIO()

        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(stderr):
            main(["export"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("the following arguments are required: --input", stderr.getvalue())

    def test_batch_command_handles_missing_file(self) -> None:
        exit_code, _, stderr = self.run_cli(["batch", "--input", "non_existent_file_path.txt"])

        self.assertEqual(exit_code, 2)
        self.assertIn("could not read batch file", stderr)
        self.assertIn("code: INVALID_INPUT", stderr)

    @patch("ytcap.commands.batch.process_batch")
    def test_batch_command_routes_to_use_case(self, mock_process: object) -> None:
        from ytcap.app.process_batch import ProcessBatchResult
        mock_process.return_value = ProcessBatchResult(
            run_id="2026-07-06T20-00-00Z",
            started_at="2026-07-06T20:00:00Z",
            finished_at="2026-07-06T20:01:00Z",
            total=10,
            ok=8,
            skipped=1,
            failed=1,
            manifest_path=Path("dummy.json"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            batch_file = Path(temp_dir) / "videos.txt"
            batch_file.write_text("abc12345678", encoding="utf-8")

            exit_code, stdout, stderr = self.run_cli([
                "batch",
                "--input",
                str(batch_file),
                "--lang",
                "tr",
                "--source",
                "manual",
                "--format",
                "vtt",
                "--out",
                "./out",
                "--dry-run",
            ])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Dry run: no files written.", stdout)

            dry_run_options = mock_process.call_args_list[0].args[0]
            self.assertEqual(dry_run_options.input, str(batch_file))
            self.assertEqual(dry_run_options.language, "tr")
            self.assertEqual(dry_run_options.source, "manual")
            self.assertEqual(dry_run_options.subtitle_format, "vtt")
            self.assertEqual(dry_run_options.output_dir, "./out")
            self.assertTrue(dry_run_options.dry_run)

            exit_code, stdout, stderr = self.run_cli([
                "batch",
                "--input",
                str(batch_file),
                "--resume",
                "--skip-existing",
                "--fail-fast",
                "--max-errors",
                "2",
                "--out",
                "./out",
            ])
            self.assertEqual(exit_code, 1)
            self.assertIn("Batch command completed.", stdout)
            self.assertIn("Total: 10", stdout)
            self.assertIn("Success: 8", stdout)
            self.assertIn("Failed: 1", stdout)

            run_options = mock_process.call_args_list[1].args[0]
            self.assertEqual(run_options.input, str(batch_file))
            self.assertEqual(run_options.output_dir, "./out")
            self.assertTrue(run_options.resume)
            self.assertTrue(run_options.skip_existing)
            self.assertTrue(run_options.fail_fast)
            self.assertEqual(run_options.max_errors, 2)
            self.assertFalse(run_options.dry_run)

    @patch("ytcap.commands.batch.process_batch")
    def test_batch_rejects_non_positive_max_errors(self, mock_process: object) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            batch_file = Path(temp_dir) / "videos.txt"
            batch_file.write_text("abc12345678", encoding="utf-8")

            exit_code, _, stderr = self.run_cli([
                "batch",
                "--input",
                str(batch_file),
                "--max-errors",
                "0",
            ])

        self.assertEqual(exit_code, 2)
        self.assertIn("--max-errors must be a positive integer", stderr)
        self.assertIn("code: INVALID_INPUT", stderr)
        mock_process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
