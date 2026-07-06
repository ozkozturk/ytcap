"""Tests for batch processing and manifest generation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.app.process_batch import ProcessBatchOptions, process_batch
from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.ytdlp_adapter import VideoSource


class FakeVideoProcessingAdapter:
    def __init__(self, metadata: dict[str, Any] | None = None, raise_error: Exception | None = None) -> None:
        self.metadata = metadata or {
            "id": "abc12345678",
            "title": "Test Video",
            "duration": 120,
            "subtitles": {
                "en": [{"ext": "srt"}]
            }
        }
        self.raise_error = raise_error
        self.calls: list[dict[str, Any]] = []

    def extract_metadata(self, source: VideoSource) -> dict[str, Any]:
        self.calls.append({"method": "extract_metadata", "source": source})
        if self.raise_error:
            raise self.raise_error
        res = dict(self.metadata)
        if source.video_id:
            res["id"] = source.video_id
        elif source.url and "abc12345678" not in source.url:
            res["id"] = "xyz98765432"
        return res

    def download_subtitle(
        self,
        source: VideoSource,
        *,
        language: str,
        subtitle_source: str,
        subtitle_format: str,
        output_path: str | Path,
    ) -> Path:
        self.calls.append({
            "method": "download_subtitle",
            "source": source,
            "language": language,
            "subtitle_source": subtitle_source,
            "subtitle_format": subtitle_format,
            "output_path": output_path,
        })
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fake subtitle content", encoding="utf-8")
        return path


class TestProcessBatch(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

        self.batch_file = self.out_dir / "batch.txt"
        self.batch_file.write_text(
            "# Comments\n"
            "abc12345678\n"
            "https://www.youtube.com/watch?v=xyz98765432 # inline comment\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_process_batch_success(self) -> None:
        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakeVideoProcessingAdapter()

        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.skipped, 0)

        manifest_path = result.manifest_path
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["schema_version"], "0.1")
        self.assertEqual(manifest["command"], "batch")
        self.assertEqual(manifest["summary"]["total"], 2)
        self.assertEqual(manifest["summary"]["ok"], 2)
        self.assertEqual(len(manifest["outputs"]), 4)
        self.assertEqual(len(manifest["errors"]), 0)

    def test_process_batch_fail_fast(self) -> None:
        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            fail_fast=True,
        )
        adapter = FakeVideoProcessingAdapter(
            raise_error=YtcapError(ErrorCode.VIDEO_UNAVAILABLE, "Video is unavailable", exit_code=3)
        )

        with self.assertRaises(YtcapError) as context:
            process_batch(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.VIDEO_UNAVAILABLE)

        manifest_files = list((self.out_dir / "runs").glob("*.manifest.json"))
        self.assertEqual(len(manifest_files), 1)
        with open(manifest_files[0], "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["summary"]["failed"], 1)
        self.assertEqual(len(manifest["errors"]), 1)

    def test_process_batch_max_errors(self) -> None:
        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            max_errors=1,
        )
        adapter = FakeVideoProcessingAdapter(
            raise_error=YtcapError(ErrorCode.SUBTITLE_NOT_FOUND, "Subtitle not found", exit_code=4)
        )

        with self.assertRaises(YtcapError) as context:
            process_batch(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertIn("batch aborted after reaching 1 errors", context.exception.message)

    def test_process_batch_rejects_non_positive_max_errors(self) -> None:
        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir / "data",
            max_errors=0,
        )

        with self.assertRaises(YtcapError) as context:
            process_batch(options, adapter=FakeVideoProcessingAdapter())

        self.assertEqual(context.exception.code, ErrorCode.INVALID_INPUT)
        self.assertEqual(context.exception.exit_code, 2)
        self.assertIn("--max-errors must be a positive integer", context.exception.message)

    def test_process_batch_rejects_empty_input_without_creating_output(self) -> None:
        empty_file = self.out_dir / "empty.txt"
        empty_file.write_text("  \n# only a comment\n", encoding="utf-8")
        output_dir = self.out_dir / "empty-output"
        options = ProcessBatchOptions(
            input=empty_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=output_dir,
        )

        with self.assertRaises(YtcapError) as context:
            process_batch(options, adapter=FakeVideoProcessingAdapter())

        self.assertEqual(context.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("did not contain any video URLs or IDs", context.exception.message)
        self.assertFalse(output_dir.exists())

    def test_process_batch_dry_run_does_not_create_output_layout(self) -> None:
        output_dir = self.out_dir / "dry-run-output"
        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=output_dir,
            dry_run=True,
        )
        adapter = FakeVideoProcessingAdapter()

        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)
        self.assertEqual(result.failed, 0)
        self.assertFalse(output_dir.exists())
        self.assertFalse(result.manifest_path.exists())
        self.assertEqual(adapter.calls, [])

    def test_process_batch_skip_existing(self) -> None:
        videos_dir = self.out_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        meta_file = videos_dir / "abc12345678.info.json"

        subtitles_dir = self.out_dir / "subtitles"
        subtitles_dir.mkdir(parents=True, exist_ok=True)
        sub_file = subtitles_dir / "abc12345678.en.manual.srt"
        sub_file.write_text("existing subtitles", encoding="utf-8")

        meta_data = {
            "schema_version": "0.1",
            "video": {"id": "abc12345678"},
            "subtitles": [
                {
                    "language": "en",
                    "source": "manual",
                    "formats": ["srt"],
                    "selected": True,
                    "downloaded": True,
                    "path": str(sub_file),
                }
            ]
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            skip_existing=True,
        )
        adapter = FakeVideoProcessingAdapter()
        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.skipped, 1)

    def test_process_batch_skip_existing_requires_matching_language_source_and_format(self) -> None:
        videos_dir = self.out_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        meta_file = videos_dir / "abc12345678.info.json"

        subtitles_dir = self.out_dir / "subtitles"
        subtitles_dir.mkdir(parents=True, exist_ok=True)
        sub_file = subtitles_dir / "abc12345678.en.manual.srt"
        sub_file.write_text("existing subtitles", encoding="utf-8")

        meta_data = {
            "schema_version": "0.1",
            "video": {"id": "abc12345678"},
            "subtitles": [
                {
                    "language": "en",
                    "source": "manual",
                    "formats": ["srt"],
                    "selected": True,
                    "downloaded": True,
                    "path": str(sub_file),
                }
            ]
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="auto",
            subtitle_format="vtt",
            output_dir=self.out_dir,
            skip_existing=True,
        )
        adapter = FakeVideoProcessingAdapter(
            metadata={
                "id": "abc12345678",
                "title": "Test Video",
                "duration": 120,
                "automatic_captions": {
                    "en": [{"ext": "vtt"}],
                },
            }
        )
        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)
        self.assertEqual(result.skipped, 0)

    def test_process_batch_skip_existing_metadata_only(self) -> None:
        videos_dir = self.out_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        meta_file = videos_dir / "abc12345678.info.json"

        meta_data = {
            "schema_version": "0.1",
            "video": {"id": "abc12345678"},
            "subtitles": [
                {
                    "language": "en",
                    "source": "manual",
                    "formats": ["srt"],
                    "selected": False,
                    "downloaded": False,
                }
            ]
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            skip_existing=True,
        )
        adapter = FakeVideoProcessingAdapter()
        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(len(adapter.calls), 4)

    def test_process_batch_resume(self) -> None:
        runs_dir = self.out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = runs_dir / "2026-07-06T20-00-00Z.manifest.json"
        manifest_data = {
            "schema_version": "0.1",
            "run_id": "2026-07-06T20-00-00Z",
            "started_at": "2026-07-06T20:00:00Z",
            "finished_at": "2026-07-06T20:01:00Z",
            "command": "batch",
            "input": {"type": "file", "path": str(self.batch_file)},
            "summary": {"total": 2, "ok": 1, "skipped": 0, "failed": 0},
            "outputs": [str(self.out_dir / "videos" / "abc12345678.info.json")],
            "errors": [],
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            resume=True,
        )
        adapter = FakeVideoProcessingAdapter()
        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.run_id, "2026-07-06T20-00-00Z")
        self.assertEqual(result.ok, 2)
        self.assertEqual(len(adapter.calls), 2)

    def test_process_batch_resume_with_skip_existing_keeps_existing_behavior(self) -> None:
        videos_dir = self.out_dir / "videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        meta_file = videos_dir / "abc12345678.info.json"

        subtitles_dir = self.out_dir / "subtitles"
        subtitles_dir.mkdir(parents=True, exist_ok=True)
        sub_file = subtitles_dir / "abc12345678.en.manual.srt"
        sub_file.write_text("existing subtitles", encoding="utf-8")

        meta_data = {
            "schema_version": "0.1",
            "video": {"id": "abc12345678"},
            "subtitles": [
                {
                    "language": "en",
                    "source": "manual",
                    "formats": ["srt"],
                    "selected": True,
                    "downloaded": True,
                    "path": str(sub_file),
                }
            ]
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            resume=True,
            skip_existing=True,
        )
        adapter = FakeVideoProcessingAdapter()
        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.skipped, 1)

    def test_process_batch_resume_retries_failures_without_stale_errors(self) -> None:
        batch_file = self.out_dir / "retry.txt"
        batch_file.write_text("abc12345678\n", encoding="utf-8")
        runs_dir = self.out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = runs_dir / "2026-07-06T20-00-00Z.manifest.json"
        manifest_data = {
            "schema_version": "0.1",
            "run_id": "2026-07-06T20-00-00Z",
            "started_at": "2026-07-06T20:00:00Z",
            "finished_at": "2026-07-06T20:01:00Z",
            "command": "batch",
            "input": {"type": "file", "path": str(batch_file)},
            "summary": {"total": 1, "ok": 0, "skipped": 0, "failed": 1},
            "outputs": [],
            "errors": [
                {
                    "video_id": "abc12345678",
                    "code": "SUBTITLE_NOT_FOUND",
                    "message": "Subtitle not found",
                }
            ],
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        options = ProcessBatchOptions(
            input=batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            resume=True,
        )
        adapter = FakeVideoProcessingAdapter()
        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.run_id, "2026-07-06T20-00-00Z")
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(adapter.calls), 2)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["ok"], 1)
        self.assertEqual(manifest["summary"]["failed"], 0)
        self.assertEqual(manifest["errors"], [])

    def test_process_batch_writes_failed_jsonl_for_non_fast_failures(self) -> None:
        options = ProcessBatchOptions(
            input=self.batch_file,
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakeVideoProcessingAdapter(
            raise_error=YtcapError(ErrorCode.SUBTITLE_NOT_FOUND, "Subtitle not found", exit_code=4)
        )

        result = process_batch(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 0)
        self.assertEqual(result.failed, 2)

        failed_path = self.out_dir / "failed" / "failed.jsonl"
        records = [
            json.loads(line)
            for line in failed_path.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["schema_version"], "0.1")
        self.assertEqual(records[0]["video_id"], "abc12345678")
        self.assertEqual(records[0]["code"], "SUBTITLE_NOT_FOUND")
