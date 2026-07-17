"""Tests for playlist processing and manifest generation."""

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

from ytcap.app.process_playlist import ProcessPlaylistOptions, process_playlist
from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.ytdlp_adapter import VideoSource


PLAYLIST_ENTRIES = [
    VideoSource(url="https://www.youtube.com/watch?v=abc12345678", video_id="abc12345678"),
    VideoSource(url="https://www.youtube.com/watch?v=xyz98765432", video_id="xyz98765432"),
    VideoSource(video_id="def55511122"),
    VideoSource(video_id="ghi66633344"),
    VideoSource(video_id="jkl77755566"),
]


class FakePlaylistVideoAdapter:
    def __init__(
        self,
        metadata: dict[str, Any] | None = None,
        raise_error: Exception | None = None,
        entries: list[VideoSource] | None = None,
    ) -> None:
        self.metadata = metadata or {
            "id": "abc12345678",
            "title": "Test Video",
            "duration": 120,
            "subtitles": {
                "en": [{"ext": "srt"}],
            },
        }
        self.raise_error = raise_error
        self._entries = entries if entries is not None else PLAYLIST_ENTRIES
        self.calls: list[dict[str, Any]] = []

    def extract_metadata(self, source: VideoSource) -> dict[str, Any]:
        self.calls.append({"method": "extract_metadata", "source": source})
        if self.raise_error:
            raise self.raise_error
        res = dict(self.metadata)
        if source.video_id:
            res["id"] = source.video_id
        return res

    def extract_playlist_entries(self, source: VideoSource) -> list[VideoSource]:
        self.calls.append({"method": "extract_playlist_entries", "source": source})
        return list(self._entries)

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


class TestProcessPlaylist(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_process_playlist_options_url_cleans_backslashes(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist\\?list\\=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        self.assertEqual(options.url, "https://www.youtube.com/playlist?list=PLabc123")

    def test_process_playlist_success(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakePlaylistVideoAdapter()

        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 5)
        self.assertEqual(result.ok, 5)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.skipped, 0)

        manifest_path = result.manifest_path
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["schema_version"], "0.1")
        self.assertEqual(manifest["command"], "playlist")
        self.assertEqual(manifest["input"]["type"], "playlist")
        self.assertEqual(manifest["input"]["url"], options.url)
        self.assertEqual(manifest["summary"]["playlist_entries"], 5)
        self.assertEqual(manifest["summary"]["total"], 5)
        self.assertEqual(manifest["summary"]["ok"], 5)
        self.assertEqual(len(manifest["outputs"]), 10)
        self.assertEqual(len(manifest["errors"]), 0)

    def test_process_playlist_with_range(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            start=2,
            end=4,
        )
        adapter = FakePlaylistVideoAdapter()

        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 3)
        self.assertEqual(result.ok, 3)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["playlist_entries"], 5)
        self.assertEqual(manifest["summary"]["total"], 3)

    def test_process_playlist_with_limit(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            limit=2,
        )
        adapter = FakePlaylistVideoAdapter()

        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)

    def test_process_playlist_start_only(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            start=3,
        )
        adapter = FakePlaylistVideoAdapter()

        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 3)
        self.assertEqual(result.ok, 3)

    def test_process_playlist_empty_playlist(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLempty",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakePlaylistVideoAdapter(entries=[])

        with self.assertRaises(YtcapError) as context:
            process_playlist(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("did not contain any videos", context.exception.message)

    def test_process_playlist_range_results_in_zero(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            start=10,
        )
        adapter = FakePlaylistVideoAdapter(entries=PLAYLIST_ENTRIES[:2])

        with self.assertRaises(YtcapError) as context:
            process_playlist(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("range or limit resulted in zero videos", context.exception.message)

    def test_process_playlist_dry_run_does_not_create_output(self) -> None:
        output_dir = self.out_dir / "dry-run-output"
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=output_dir,
            dry_run=True,
        )
        adapter = FakePlaylistVideoAdapter()

        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 5)
        self.assertEqual(result.ok, 5)
        self.assertFalse(output_dir.exists())

    def test_process_playlist_fail_fast(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            fail_fast=True,
        )
        adapter = FakePlaylistVideoAdapter(
            entries=PLAYLIST_ENTRIES[:2],
            raise_error=YtcapError(ErrorCode.VIDEO_UNAVAILABLE, "Video is unavailable", exit_code=3),
        )

        with self.assertRaises(YtcapError) as context:
            process_playlist(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.VIDEO_UNAVAILABLE)

        manifest_files = list((self.out_dir / "runs").glob("*.manifest.json"))
        self.assertEqual(len(manifest_files), 1)
        with open(manifest_files[0], "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["summary"]["failed"], 1)
        self.assertEqual(len(manifest["errors"]), 1)

    def test_process_playlist_max_errors(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            max_errors=1,
        )
        adapter = FakePlaylistVideoAdapter(
            entries=PLAYLIST_ENTRIES[:3],
            raise_error=YtcapError(ErrorCode.SUBTITLE_NOT_FOUND, "Subtitle not found", exit_code=4),
        )

        with self.assertRaises(YtcapError) as context:
            process_playlist(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertIn("playlist processing aborted after reaching 1 errors", context.exception.message)

    def test_process_playlist_skip_existing(self) -> None:
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
            ],
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            skip_existing=True,
        )
        adapter = FakePlaylistVideoAdapter(entries=PLAYLIST_ENTRIES[:2])
        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.skipped, 1)

    def test_process_playlist_skip_existing_requires_matching_language_source_and_format(self) -> None:
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
            ],
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_data, f)

        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="tr",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            skip_existing=True,
        )
        adapter = FakePlaylistVideoAdapter(
            metadata={
                "id": "abc12345678",
                "title": "Test Video",
                "duration": 120,
                "subtitles": {
                    "tr": [{"ext": "srt"}],
                },
            },
            entries=PLAYLIST_ENTRIES[:2],
        )
        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)
        self.assertEqual(result.skipped, 0)

    def test_process_playlist_resume(self) -> None:
        runs_dir = self.out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = runs_dir / "2026-07-06T20-00-00Z.manifest.json"
        manifest_data = {
            "schema_version": "0.1",
            "run_id": "2026-07-06T20-00-00Z",
            "started_at": "2026-07-06T20:00:00Z",
            "finished_at": "2026-07-06T20:01:00Z",
            "command": "playlist",
            "input": {"type": "playlist", "url": "https://www.youtube.com/playlist?list=PLabc123"},
            "options": {
                "language": "en",
                "source": "any",
                "format": "srt",
                "limit": None,
                "start": 1,
                "end": None,
            },
            "summary": {"playlist_entries": 2, "total": 2, "ok": 1, "skipped": 0, "failed": 0},
            "outputs": [str(self.out_dir / "videos" / "abc12345678.info.json")],
            "errors": [],
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            resume=True,
        )
        adapter = FakePlaylistVideoAdapter(entries=PLAYLIST_ENTRIES[:2])
        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.run_id, "2026-07-06T20-00-00Z")
        self.assertEqual(result.ok, 2)
        self.assertEqual(len(adapter.calls), 3)

    def test_process_playlist_resume_uses_matching_manifest_not_newer_batch_manifest(self) -> None:
        runs_dir = self.out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        playlist_manifest = runs_dir / "2026-07-06T20-00-00Z.manifest.json"
        playlist_manifest_data = {
            "schema_version": "0.1",
            "run_id": "2026-07-06T20-00-00Z",
            "started_at": "2026-07-06T20:00:00Z",
            "finished_at": "2026-07-06T20:01:00Z",
            "command": "playlist",
            "input": {"type": "playlist", "url": "https://www.youtube.com/playlist?list=PLabc123"},
            "options": {
                "language": "en",
                "source": "any",
                "format": "srt",
                "limit": None,
                "start": 1,
                "end": None,
            },
            "summary": {"playlist_entries": 2, "total": 2, "ok": 1, "skipped": 0, "failed": 0},
            "outputs": [str(self.out_dir / "videos" / "abc12345678.info.json")],
            "errors": [],
        }
        playlist_manifest.write_text(json.dumps(playlist_manifest_data), encoding="utf-8")

        batch_manifest = runs_dir / "2026-07-06T21-00-00Z.manifest.json"
        batch_manifest_data = {
            "schema_version": "0.1",
            "run_id": "2026-07-06T21-00-00Z",
            "started_at": "2026-07-06T21:00:00Z",
            "finished_at": "2026-07-06T21:01:00Z",
            "command": "batch",
            "input": {"type": "file", "path": "videos.txt"},
            "options": {},
            "summary": {"total": 1, "ok": 1, "skipped": 0, "failed": 0},
            "outputs": [str(self.out_dir / "videos" / "wrong000000.info.json")],
            "errors": [],
        }
        batch_manifest.write_text(json.dumps(batch_manifest_data), encoding="utf-8")

        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            resume=True,
        )
        adapter = FakePlaylistVideoAdapter(entries=PLAYLIST_ENTRIES[:2])
        result = process_playlist(options, adapter=adapter)

        self.assertEqual(result.run_id, "2026-07-06T20-00-00Z")
        self.assertEqual(result.ok, 2)
        self.assertEqual(len(adapter.calls), 3)

    def test_process_playlist_resume_ignores_different_playlist_or_options(self) -> None:
        runs_dir = self.out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = runs_dir / "2026-07-06T20-00-00Z.manifest.json"
        manifest_data = {
            "schema_version": "0.1",
            "run_id": "2026-07-06T20-00-00Z",
            "started_at": "2026-07-06T20:00:00Z",
            "finished_at": "2026-07-06T20:01:00Z",
            "command": "playlist",
            "input": {"type": "playlist", "url": "https://www.youtube.com/playlist?list=PLdifferent"},
            "options": {
                "language": "en",
                "source": "any",
                "format": "srt",
                "limit": 1,
                "start": 1,
                "end": None,
            },
            "summary": {"playlist_entries": 2, "total": 1, "ok": 1, "skipped": 0, "failed": 0},
            "outputs": [str(self.out_dir / "videos" / "abc12345678.info.json")],
            "errors": [],
        }
        manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            resume=True,
        )
        adapter = FakePlaylistVideoAdapter(entries=PLAYLIST_ENTRIES[:2])
        result = process_playlist(options, adapter=adapter)

        self.assertNotEqual(result.run_id, "2026-07-06T20-00-00Z")
        self.assertEqual(result.ok, 2)
        self.assertEqual(len(adapter.calls), 5)

    def test_process_playlist_writes_failed_jsonl(self) -> None:
        options = ProcessPlaylistOptions(
            url="https://www.youtube.com/playlist?list=PLabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakePlaylistVideoAdapter(
            entries=PLAYLIST_ENTRIES[:2],
            raise_error=YtcapError(ErrorCode.SUBTITLE_NOT_FOUND, "Subtitle not found", exit_code=4),
        )

        result = process_playlist(options, adapter=adapter)

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
        self.assertEqual(records[0]["code"], "SUBTITLE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
