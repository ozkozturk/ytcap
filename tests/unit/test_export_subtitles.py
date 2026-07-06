"""Subtitle export use-case tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.app.export_subtitles import ExportSubtitlesOptions, export_subtitles  # noqa: E402
from ytcap.errors import ErrorCode, YtcapError  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class ExportSubtitlesTest(unittest.TestCase):
    def test_single_srt_file_exports_cue_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "abc123.en.manual.srt"
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="cue",
                    output_dir=root / "normalized",
                )
            )

            output_path = root / "normalized" / "abc123.en.cue.jsonl"
            records = read_jsonl(output_path)
            self.assertEqual(len(result.files), 1)
            self.assertEqual(result.files[0].output_path, output_path)
            self.assertEqual(result.files[0].source, "manual")
            self.assertEqual(result.files[0].segment_count, 3)
            self.assertEqual(records[0]["type"], "cue")
            self.assertEqual(records[0]["video_id"], "abc123")
            self.assertEqual(records[0]["language"], "en")
            self.assertEqual(records[0]["source"], "manual")

    def test_single_vtt_file_exports_sentence_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "abc123.en.auto.vtt"
            subtitle_path.write_text(fixture_text("sample.en.vtt"), encoding="utf-8")

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="sentence",
                    output_dir=root / "normalized",
                )
            )

            output_path = root / "normalized" / "abc123.en.sentence.jsonl"
            records = read_jsonl(output_path)
            self.assertEqual(result.files[0].source, "auto")
            self.assertEqual(result.files[0].segment_count, len(records))
            self.assertGreater(len(records), 0)
            self.assertEqual(records[0]["type"], "sentence")
            self.assertEqual(records[0]["source"], "auto")
            self.assertIn("timing_strategy", records[0])

    def test_directory_export_processes_supported_files_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "subtitles"
            input_dir.mkdir()
            (input_dir / "zeta.en.manual.srt").write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            (input_dir / "alpha.tr.auto.vtt").write_text(fixture_text("sample.en.vtt"), encoding="utf-8")
            (input_dir / "ignored.txt").write_text("not subtitles\n", encoding="utf-8")

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=input_dir,
                    segments="cue",
                    output_dir=root / "normalized",
                )
            )

            self.assertEqual(
                [item.input_path.name for item in result.files],
                ["alpha.tr.auto.vtt", "zeta.en.manual.srt"],
            )
            self.assertTrue((root / "normalized" / "alpha.tr.cue.jsonl").is_file())
            self.assertTrue((root / "normalized" / "zeta.en.cue.jsonl").is_file())
            self.assertEqual([item.source for item in result.files], ["auto", "manual"])

    def test_filename_without_source_uses_unknown_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "abc123.en.srt"
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="cue",
                    output_dir=root / "normalized",
                )
            )

            records = read_jsonl(root / "normalized" / "abc123.en.cue.jsonl")
            self.assertEqual(records[0]["source"], "unknown")

    def test_filename_source_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "abc123.en.MANUAL.srt"
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="cue",
                    output_dir=root / "normalized",
                )
            )

            records = read_jsonl(root / "normalized" / "abc123.en.cue.jsonl")
            self.assertEqual(records[0]["source"], "manual")

    def test_single_file_overrides_video_id_and_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "input.srt"
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="cue",
                    output_dir=root / "normalized",
                    video_id="abc123",
                    language="tr",
                )
            )

            self.assertEqual(result.files[0].video_id, "abc123")
            self.assertEqual(result.files[0].language, "tr")
            self.assertEqual(result.files[0].source, "unknown")
            self.assertTrue((root / "normalized" / "abc123.tr.cue.jsonl").is_file())

    def test_missing_input_returns_invalid_input(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            export_subtitles(
                ExportSubtitlesOptions(
                    input_path="missing.srt",
                    segments="cue",
                    output_dir="normalized",
                )
            )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertEqual(raised.exception.exit_code, 2)

    def test_single_file_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "abc123.en.txt"
            path.write_text("not subtitles\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=path,
                        segments="cue",
                        output_dir=Path(temp_dir) / "normalized",
                    )
                )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("unsupported subtitle file extension", raised.exception.message)

    def test_empty_matching_directory_returns_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "subtitles"
            input_dir.mkdir()
            (input_dir / "notes.txt").write_text("ignored\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=Path(temp_dir) / "normalized",
                    )
                )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("no SRT/VTT subtitle files found", raised.exception.message)

    def test_unreadable_directory_returns_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "subtitles"
            input_dir.mkdir()

            with patch("ytcap.app.export_subtitles.Path.iterdir", side_effect=OSError("permission denied")):
                with self.assertRaises(YtcapError) as raised:
                    export_subtitles(
                        ExportSubtitlesOptions(
                            input_path=input_dir,
                            segments="cue",
                            output_dir=Path(temp_dir) / "normalized",
                        )
                    )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("could not read input directory", raised.exception.message)

    def test_directory_input_rejects_metadata_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "subtitles"
            input_dir.mkdir()
            (input_dir / "abc123.en.manual.srt").write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=Path(temp_dir) / "normalized",
                        video_id="override",
                    )
                )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("can only be used with a single subtitle file", raised.exception.message)

    def test_directory_supported_file_requires_filename_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "subtitles"
            input_dir.mkdir()
            (input_dir / "only.srt").write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=Path(temp_dir) / "normalized",
                    )
                )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("could not infer video id and language", raised.exception.message)

    def test_directory_rejects_duplicate_output_paths_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "subtitles"
            output_path = root / "normalized" / "abc123.en.cue.jsonl"
            input_dir.mkdir()
            (input_dir / "abc123.en.auto.vtt").write_text(
                fixture_text("sample.en.vtt"),
                encoding="utf-8",
            )
            (input_dir / "abc123.en.manual.srt").write_text(
                fixture_text("sample.en.srt"),
                encoding="utf-8",
            )

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=root / "normalized",
                    )
                )

            self.assertFalse(output_path.exists())

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("multiple subtitle files map to the same output file", raised.exception.message)

    def test_existing_later_output_rejects_before_partial_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "subtitles"
            output_dir = root / "normalized"
            first_output_path = output_dir / "alpha.en.cue.jsonl"
            existing_output_path = output_dir / "zeta.en.cue.jsonl"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "alpha.en.manual.srt").write_text(
                fixture_text("sample.en.srt"),
                encoding="utf-8",
            )
            (input_dir / "zeta.en.manual.srt").write_text(
                fixture_text("sample.en.srt"),
                encoding="utf-8",
            )
            existing_output_path.write_text("existing\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=output_dir,
                    )
                )

            self.assertFalse(first_output_path.exists())
            self.assertEqual(existing_output_path.read_text(encoding="utf-8"), "existing\n")

        self.assertEqual(raised.exception.code, ErrorCode.OUTPUT_WRITE_FAILED)
        self.assertEqual(raised.exception.exit_code, 5)
        self.assertIn("remove it or choose another --out directory", raised.exception.message)

    def test_later_parse_error_rejects_before_partial_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "subtitles"
            output_dir = root / "normalized"
            first_output_path = output_dir / "alpha.en.cue.jsonl"
            input_dir.mkdir()
            (input_dir / "alpha.en.manual.srt").write_text(
                fixture_text("sample.en.srt"),
                encoding="utf-8",
            )
            (input_dir / "zeta.en.manual.srt").write_text(
                fixture_text("malformed.srt"),
                encoding="utf-8",
            )

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=output_dir,
                    )
                )

            self.assertFalse(first_output_path.exists())

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertIn("malformed SRT block", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
