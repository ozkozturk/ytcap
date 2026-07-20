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


def sample_metadata(video_id: str) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "video": {
            "id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
            "title": f"Video {video_id}",
            "duration_seconds": 320,
            "upload_date": "20260101",
        },
        "channel": {
            "id": "channel123",
            "name": "Example Channel",
            "url": "https://www.youtube.com/channel/channel123",
        },
        "subtitles": [
            {
                "language": "en",
                "source": "manual",
                "formats": ["srt"],
                "selected": True,
                "downloaded": True,
                "path": f"data/subtitles/{video_id}.en.manual.srt",
            },
            {
                "language": "en-GB",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "tr",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "de",
                "source": "auto",
                "formats": ["vtt"],
                "selected": False,
                "downloaded": True,
                "path": f"data/subtitles/{video_id}.de.auto.vtt",
            },
        ],
    }


def write_metadata(root: Path, video_id: str, payload: dict[str, object] | None = None) -> Path:
    metadata_path = root / "videos" / f"{video_id}.info.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload if payload is not None else sample_metadata(video_id)) + "\n",
        encoding="utf-8",
    )
    return metadata_path


class ExportSubtitlesTest(unittest.TestCase):
    def test_single_srt_file_exports_cue_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "abc123.en.manual.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            write_metadata(root, "abc123")

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
            self.assertIn("normalized_text", records[0])
            self.assertEqual(records[0]["channel_name"], "Example Channel")
            self.assertEqual(records[0]["video_title"], "Video abc123")
            self.assertEqual(records[0]["available_manual_subtitles"], ["tr"])
            self.assertEqual(records[0]["downloaded_subtitles"], ["de"])
            self.assertIsNone(records[0]["dataset_category"])
            self.assertEqual(records[0]["category_source"], "none")

    def test_single_vtt_file_exports_sentence_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "abc123.en.auto.vtt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.vtt"), encoding="utf-8")
            write_metadata(root, "abc123")

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
            self.assertIn("normalized_text", records[0])
            self.assertEqual(records[0]["channel_id"], "channel123")
            self.assertIn("timing_strategy", records[0])

    def test_sentence_export_handles_mid_cue_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "midcue001.en.manual.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("midcue001.en.manual.srt"), encoding="utf-8")
            write_metadata(root, "midcue001")

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="sentence",
                    output_dir=root / "normalized",
                )
            )

            output_path = root / "normalized" / "midcue001.en.sentence.jsonl"
            records = read_jsonl(output_path)
            self.assertEqual(result.files[0].segment_count, 3)
            self.assertEqual(len(records), 3)

            first, second, third = records
            self.assertEqual(first["text"], "than here.")
            self.assertEqual(first["cue_coverage"], "single")
            self.assertEqual(first["timing_precision"], "estimated_both")

            self.assertEqual(
                second["text"],
                'And none of us can say "Boo," because none of us have ever been to prison.',
            )
            self.assertEqual(second["cue_coverage"], "multiple")
            self.assertEqual(second["timing_precision"], "estimated_both")
            self.assertEqual(second["cue_count"], 3)
            self.assertEqual(second["start_cue_index"], 1)
            self.assertEqual(second["end_cue_index"], 3)
            self.assertGreater(second["start"], 1.0)
            self.assertLess(second["start"], 3.5)
            self.assertGreater(second["end"], 8.3)
            self.assertLess(second["end"], 11.0)
            self.assertLessEqual(second["playback_start"], second["start"])
            self.assertGreaterEqual(second["playback_end"], second["end"])

            self.assertEqual(
                third["text"],
                "The next sentence starts right here and ends now.",
            )
            self.assertEqual(third["timing_precision"], "estimated_start")
            self.assertEqual(third["end"], 14.0)

            starts = [record["start"] for record in records]
            ends = [record["end"] for record in records]
            for index in range(len(records)):
                self.assertLessEqual(starts[index], ends[index])
                if index > 0:
                    self.assertGreaterEqual(starts[index], ends[index - 1])

    def test_sentence_export_handles_abbreviations_and_technical_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "techtalk01.en.manual.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("techtalk01.en.manual.srt"), encoding="utf-8")
            write_metadata(root, "techtalk01")

            result = export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="sentence",
                    output_dir=root / "normalized",
                )
            )

            output_path = root / "normalized" / "techtalk01.en.sentence.jsonl"
            records = read_jsonl(output_path)
            self.assertEqual(result.files[0].segment_count, 4)
            self.assertEqual(
                [record["text"] for record in records],
                [
                    "Dr. Smith explained Node.js today.",
                    "We use v2.4.1 and React.js, e.g. in class.",
                    "Visit example.com for details.",
                    "Mr. Brown agreed.",
                ],
            )
            self.assertEqual(records[0]["timing_precision"], "cue_aligned")
            self.assertEqual(records[1]["timing_precision"], "cue_aligned")
            self.assertEqual(records[2]["timing_precision"], "estimated_end")
            self.assertEqual(records[3]["timing_precision"], "estimated_start")
            self.assertEqual(records[2]["normalized_text"], "visit example com for details")
            for record in records:
                self.assertEqual(record["boundary_engine"], "punctuation-v2")
                self.assertLessEqual(record["playback_start"], record["start"])
                self.assertGreaterEqual(record["playback_end"], record["end"])

    def test_directory_export_processes_supported_files_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "subtitles"
            input_dir.mkdir()
            (input_dir / "zeta.en.manual.srt").write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            (input_dir / "alpha.tr.auto.vtt").write_text(fixture_text("sample.en.vtt"), encoding="utf-8")
            (input_dir / "ignored.txt").write_text("not subtitles\n", encoding="utf-8")
            write_metadata(root, "zeta")
            write_metadata(root, "alpha")

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
            subtitle_path = root / "subtitles" / "abc123.en.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            write_metadata(root, "abc123")

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
            subtitle_path = root / "subtitles" / "abc123.en.MANUAL.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            write_metadata(root, "abc123")

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
            write_metadata(root, "abc123")

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

    def test_missing_metadata_fields_export_as_null(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "abc123.en.manual.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            write_metadata(root, "abc123", payload={"schema_version": "0.1"})

            export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="cue",
                    output_dir=root / "normalized",
                )
            )

            records = read_jsonl(root / "normalized" / "abc123.en.cue.jsonl")
            self.assertIsNone(records[0]["channel_id"])
            self.assertIsNone(records[0]["channel_name"])
            self.assertIsNone(records[0]["video_title"])
            self.assertIsNone(records[0]["available_manual_subtitles"])
            self.assertIsNone(records[0]["downloaded_subtitles"])

    def test_category_exports_user_dataset_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "abc123.en.manual.srt"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            write_metadata(root, "abc123")

            export_subtitles(
                ExportSubtitlesOptions(
                    input_path=subtitle_path,
                    segments="cue",
                    output_dir=root / "normalized",
                    category=" education ",
                )
            )

            records = read_jsonl(root / "normalized" / "abc123.en.cue.jsonl")
            self.assertEqual(records[0]["dataset_category"], "education")
            self.assertEqual(records[0]["category_source"], "user")

    def test_empty_category_returns_invalid_input(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            export_subtitles(
                ExportSubtitlesOptions(
                    input_path="missing.srt",
                    segments="cue",
                    output_dir="normalized",
                    category="  ",
                )
            )

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("--category must not be empty", raised.exception.message)

    def test_ambiguous_metadata_layout_rejects_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "input.srt"
            output_path = root / "jsonl" / "abc123.en.cue.jsonl"
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=subtitle_path,
                        segments="cue",
                        output_dir=root / "jsonl",
                        video_id="abc123",
                        language="en",
                    )
                )

            self.assertFalse(output_path.exists())

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("could not infer standard output layout", raised.exception.message)

    def test_missing_metadata_file_rejects_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "abc123.en.manual.srt"
            output_path = root / "normalized" / "abc123.en.cue.jsonl"
            subtitle_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=subtitle_path,
                        segments="cue",
                        output_dir=root / "normalized",
                    )
                )

            self.assertFalse(output_path.exists())

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("metadata file not found", raised.exception.message)

    def test_invalid_metadata_json_rejects_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "subtitles" / "abc123.en.manual.srt"
            output_path = root / "normalized" / "abc123.en.cue.jsonl"
            metadata_path = root / "videos" / "abc123.info.json"
            subtitle_path.parent.mkdir()
            metadata_path.parent.mkdir()
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")
            metadata_path.write_text("{not json\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=subtitle_path,
                        segments="cue",
                        output_dir=root / "normalized",
                    )
                )

            self.assertFalse(output_path.exists())

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertIn("could not parse metadata JSON", raised.exception.message)

    def test_single_file_rejects_unsafe_video_id_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subtitle_path = root / "input.srt"
            subtitle_path.write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=subtitle_path,
                        segments="cue",
                        output_dir=root / "normalized",
                        video_id="../escape",
                        language="en",
                    )
                )

            self.assertFalse((root / "escape.en.cue.jsonl").exists())

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("unsafe filename", raised.exception.message)

    def test_directory_rejects_unsafe_inferred_filename_parts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_dir = root / "subtitles"
            input_dir.mkdir()
            (input_dir / "bad\\id.en.manual.srt").write_text(fixture_text("sample.en.srt"), encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                export_subtitles(
                    ExportSubtitlesOptions(
                        input_path=input_dir,
                        segments="cue",
                        output_dir=root / "normalized",
                    )
                )

            self.assertFalse((root / "normalized").exists())

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("unsafe filename", raised.exception.message)

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
            write_metadata(root, "alpha")
            write_metadata(root, "zeta")

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
