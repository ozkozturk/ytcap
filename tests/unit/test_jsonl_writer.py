"""JSONL writer tests."""

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

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.exporters.jsonl_writer import (  # noqa: E402
    cue_jsonl_record,
    sentence_jsonl_record,
    write_cue_jsonl_file,
    write_sentence_jsonl_file,
)
from ytcap.models.subtitle import SubtitleCue, SubtitleSentence  # noqa: E402


def sample_cues() -> list[SubtitleCue]:
    return [
        SubtitleCue(index=1, start=1.0, end=3.5, text="Hello."),
        SubtitleCue(index=2, start=4.25, end=6.0, text="Second cue."),
    ]


def sample_sentences() -> list[SubtitleSentence]:
    return [
        SubtitleSentence(
            index=1,
            start=1.0,
            end=3.5,
            text="Hello.",
            timing_strategy="cue_exact",
        ),
        SubtitleSentence(
            index=2,
            start=4.25,
            end=6.0,
            text="Second sentence.",
            timing_strategy="heuristic",
        ),
    ]


class JsonlWriterTest(unittest.TestCase):
    def test_cue_jsonl_record_matches_output_schema(self) -> None:
        record = cue_jsonl_record(
            SubtitleCue(index=1, start=1.0, end=3.5, text="Hello."),
            video_id="abc123",
            language="en",
            source="manual",
        )

        self.assertEqual(
            record,
            {
                "schema_version": "0.1",
                "type": "cue",
                "video_id": "abc123",
                "language": "en",
                "source": "manual",
                "start": 1.0,
                "end": 3.5,
                "text": "Hello.",
                "normalized_text": "hello",
                "cue_index": 1,
            },
        )

    def test_sentence_jsonl_record_matches_output_schema(self) -> None:
        record = sentence_jsonl_record(
            SubtitleSentence(
                index=1,
                start=1.0,
                end=3.5,
                text="Hello.",
                timing_strategy="cue_exact",
            ),
            video_id="abc123",
            language="en",
            source="manual",
        )

        self.assertEqual(
            record,
            {
                "schema_version": "0.1",
                "type": "sentence",
                "video_id": "abc123",
                "language": "en",
                "source": "manual",
                "start": 1.0,
                "end": 3.5,
                "text": "Hello.",
                "normalized_text": "hello",
                "sentence_index": 1,
                "timing_strategy": "cue_exact",
            },
        )

    def test_cue_jsonl_record_includes_metadata_enrichment(self) -> None:
        record = cue_jsonl_record(
            SubtitleCue(index=1, start=1.0, end=3.5, text="I can't wait;"),
            video_id="abc123",
            language="en",
            source="manual",
            metadata_enrichment={
                "channel_id": "channel123",
                "channel_name": "Example Channel",
                "channel_url": "https://example.com/channel",
                "video_title": "Example Video",
                "video_url": "https://www.youtube.com/watch?v=abc123",
                "video_webpage_url": "https://www.youtube.com/watch?v=abc123",
                "video_duration_seconds": 320,
                "video_upload_date": "20260101",
                "available_manual_subtitles": ["tr"],
                "downloaded_subtitles": ["tr"],
                "dataset_category": "education",
                "category_source": "user",
            },
        )

        self.assertEqual(record["normalized_text"], "i cant wait")
        self.assertEqual(record["channel_name"], "Example Channel")
        self.assertEqual(record["video_title"], "Example Video")
        self.assertEqual(record["available_manual_subtitles"], ["tr"])
        self.assertEqual(record["dataset_category"], "education")
        self.assertEqual(record["category_source"], "user")

    def test_write_cue_jsonl_file_writes_one_record_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "normalized" / "abc123.en.cue.jsonl"

            written = write_cue_jsonl_file(
                output_path,
                sample_cues(),
                video_id="abc123",
                language="en",
                source="manual",
            )

            self.assertTrue(written)
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["video_id"], "abc123")
            self.assertEqual(first["language"], "en")
            self.assertEqual(first["source"], "manual")
            self.assertEqual(first["cue_index"], 1)
            self.assertEqual(second["start"], 4.25)

    def test_write_sentence_jsonl_file_writes_one_record_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "normalized" / "abc123.en.sentence.jsonl"

            written = write_sentence_jsonl_file(
                output_path,
                sample_sentences(),
                video_id="abc123",
                language="en",
                source="manual",
            )

            self.assertTrue(written)
            lines = output_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            second = json.loads(lines[1])
            self.assertEqual(first["type"], "sentence")
            self.assertEqual(first["sentence_index"], 1)
            self.assertEqual(first["timing_strategy"], "cue_exact")
            self.assertEqual(second["text"], "Second sentence.")

    def test_write_cue_jsonl_file_rejects_existing_output_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "abc123.en.cue.jsonl"
            output_path.write_text("old\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                write_cue_jsonl_file(
                    output_path,
                    sample_cues(),
                    video_id="abc123",
                    language="en",
                    source="manual",
                )

            self.assertEqual(raised.exception.code, ErrorCode.OUTPUT_WRITE_FAILED)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "old\n")

    def test_write_cue_jsonl_file_can_skip_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "abc123.en.cue.jsonl"
            output_path.write_text("old\n", encoding="utf-8")

            written = write_cue_jsonl_file(
                output_path,
                sample_cues(),
                video_id="abc123",
                language="en",
                source="manual",
                skip_existing=True,
            )

            self.assertFalse(written)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "old\n")

    def test_write_cue_jsonl_file_can_overwrite_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "abc123.en.cue.jsonl"
            output_path.write_text("old\n", encoding="utf-8")

            written = write_cue_jsonl_file(
                output_path,
                sample_cues(),
                video_id="abc123",
                language="en",
                source="manual",
                overwrite=True,
            )

            self.assertTrue(written)
            self.assertNotEqual(output_path.read_text(encoding="utf-8"), "old\n")

    def test_write_cue_jsonl_file_wraps_write_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "abc123.en.cue.jsonl"
            with patch("ytcap.exporters.jsonl_writer.Path.write_text", side_effect=OSError("disk full")):
                with self.assertRaises(YtcapError) as raised:
                    write_cue_jsonl_file(
                        output_path,
                        sample_cues(),
                        video_id="abc123",
                        language="en",
                        source="manual",
                    )

            self.assertEqual(raised.exception.code, ErrorCode.OUTPUT_WRITE_FAILED)
            self.assertEqual(raised.exception.exit_code, 5)


if __name__ == "__main__":
    unittest.main()
