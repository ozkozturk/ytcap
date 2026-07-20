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
            playback_start=0.75,
            playback_end=3.9,
            cue_coverage="single",
            timing_precision="cue_aligned",
            start_cue_index=1,
            end_cue_index=1,
            cue_count=1,
            start_char_in_first_cue=0,
            end_char_in_last_cue=6,
            boundary_engine="punctuation-v2",
        ),
        SubtitleSentence(
            index=2,
            start=4.25,
            end=6.0,
            text="Second sentence.",
            timing_strategy="heuristic",
            playback_start=4.0,
            playback_end=6.4,
            cue_coverage="single",
            timing_precision="estimated_start",
            start_cue_index=2,
            end_cue_index=2,
            cue_count=1,
            start_char_in_first_cue=5,
            end_char_in_last_cue=21,
            boundary_engine="punctuation-v2",
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
                playback_start=0.75,
                playback_end=3.9,
                cue_coverage="single",
                timing_precision="cue_aligned",
                start_cue_index=1,
                end_cue_index=1,
                cue_count=1,
                start_char_in_first_cue=0,
                end_char_in_last_cue=6,
                boundary_engine="punctuation-v2",
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
                "cue_coverage": "single",
                "timing_precision": "cue_aligned",
                "playback_start": 0.75,
                "playback_end": 3.9,
                "start_cue_index": 1,
                "end_cue_index": 1,
                "cue_count": 1,
                "start_char_in_first_cue": 0,
                "end_char_in_last_cue": 6,
                "boundary_engine": "punctuation-v2",
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
            self.assertEqual(first["cue_coverage"], "single")
            self.assertEqual(first["timing_precision"], "cue_aligned")
            self.assertEqual(first["playback_start"], 0.75)
            self.assertEqual(first["playback_end"], 3.9)
            self.assertEqual(first["start_cue_index"], 1)
            self.assertEqual(first["boundary_engine"], "punctuation-v2")
            self.assertEqual(second["text"], "Second sentence.")
            self.assertEqual(second["timing_precision"], "estimated_start")

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
