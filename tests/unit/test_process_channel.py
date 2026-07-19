"""Tests for channel processing and manifest generation."""

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

from ytcap.app.process_channel import ProcessChannelOptions, process_channel
from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.ytdlp_adapter import VideoSource


CHANNEL_ENTRIES = [
    VideoSource(url="https://www.youtube.com/watch?v=abc12345678", video_id="abc12345678"),
    VideoSource(url="https://www.youtube.com/watch?v=xyz98765432", video_id="xyz98765432"),
    VideoSource(video_id="def55511122"),
    VideoSource(video_id="ghi66633344"),
    VideoSource(video_id="jkl77755566"),
]


class FakeChannelVideoAdapter:
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
        self._entries = entries if entries is not None else CHANNEL_ENTRIES
        self.calls: list[dict[str, Any]] = []

    def extract_metadata(self, source: VideoSource) -> dict[str, Any]:
        self.calls.append({"method": "extract_metadata", "source": source})
        if self.raise_error:
            if isinstance(self.raise_error, dict):
                err = self.raise_error.get(source.video_id)
                if err:
                    raise err
            else:
                raise self.raise_error
        res = dict(self.metadata)
        if source.video_id:
            res["id"] = source.video_id
        return res

    def extract_channel_entries(self, source: VideoSource, *, playlist_end: int | None = None) -> list[VideoSource]:
        self.calls.append({"method": "extract_channel_entries", "source": source, "playlist_end": playlist_end})
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


class TestProcessChannel(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_process_channel_options_url_cleans_backslashes(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel\\?list\\=UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        self.assertEqual(options.url, "https://www.youtube.com/channel?list=UCabc123")

    def test_normalize_channel_url(self) -> None:
        from ytcap.app.process_channel import normalize_channel_url
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/@TED"),
            "https://www.youtube.com/@TED/videos"
        )
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/@TED/"),
            "https://www.youtube.com/@TED/videos"
        )
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/@TED/videos"),
            "https://www.youtube.com/@TED/videos"
        )
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/@TED/shorts"),
            "https://www.youtube.com/@TED/shorts"
        )
        self.assertEqual(
            normalize_channel_url("https://www.youtube.com/channel/UCabc123"),
            "https://www.youtube.com/channel/UCabc123/videos"
        )

    def test_process_channel_success(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakeChannelVideoAdapter()

        result = process_channel(options, adapter=adapter)

        self.assertEqual(result.total, 5)
        self.assertEqual(result.ok, 5)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.skipped, 0)

        manifest_path = result.manifest_path
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["schema_version"], "0.1")
        self.assertEqual(manifest["command"], "channel")
        self.assertEqual(manifest["input"]["type"], "channel")
        self.assertEqual(manifest["input"]["url"], options.url)
        self.assertEqual(manifest["summary"]["channel_entries"], 5)
        self.assertEqual(manifest["summary"]["total"], 5)
        self.assertEqual(manifest["summary"]["ok"], 5)
        self.assertEqual(len(manifest["outputs"]), 10)
        self.assertEqual(len(manifest["errors"]), 0)

    def test_process_channel_with_range(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            start=2,
            end=4,
        )
        adapter = FakeChannelVideoAdapter()

        result = process_channel(options, adapter=adapter)

        self.assertEqual(result.total, 3)
        self.assertEqual(result.ok, 3)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["channel_entries"], 5)
        self.assertEqual(manifest["summary"]["total"], 3)

    def test_process_channel_with_limit(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            limit=2,
        )
        adapter = FakeChannelVideoAdapter()

        result = process_channel(options, adapter=adapter)

        self.assertEqual(result.total, 2)
        self.assertEqual(result.ok, 2)

    def test_process_channel_start_only(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            start=3,
        )
        adapter = FakeChannelVideoAdapter()

        result = process_channel(options, adapter=adapter)

        self.assertEqual(result.total, 3)
        self.assertEqual(result.ok, 3)

    def test_process_channel_empty_channel(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCempty",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
        )
        adapter = FakeChannelVideoAdapter(entries=[])

        with self.assertRaises(YtcapError) as context:
            process_channel(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("channel did not contain any videos", context.exception.message)

    def test_process_channel_range_results_in_zero(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            start=10,
        )
        adapter = FakeChannelVideoAdapter(entries=CHANNEL_ENTRIES[:2])

        with self.assertRaises(YtcapError) as context:
            process_channel(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("range or limit resulted in zero videos", context.exception.message)

    def test_process_channel_dry_run_does_not_create_output(self) -> None:
        output_dir = self.out_dir / "dry-run-output"
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=output_dir,
            dry_run=True,
        )
        adapter = FakeChannelVideoAdapter()

        result = process_channel(options, adapter=adapter)

        self.assertEqual(result.total, 5)
        self.assertEqual(result.ok, 5)
        self.assertFalse(output_dir.exists())

    def test_process_channel_fail_fast(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            fail_fast=True,
        )
        adapter = FakeChannelVideoAdapter(
            entries=CHANNEL_ENTRIES[:2],
            raise_error=YtcapError(ErrorCode.VIDEO_UNAVAILABLE, "Video is unavailable", exit_code=3),
        )

        with self.assertRaises(YtcapError) as context:
            process_channel(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.VIDEO_UNAVAILABLE)

        manifest_path = self.out_dir / "runs" / f"{Path(self.out_dir).name}.manifest.json"
        manifest_files = list((self.out_dir / "runs").glob("*.manifest.json"))
        self.assertEqual(len(manifest_files), 1)
        with open(manifest_files[0], "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["summary"]["total"], 2)
        self.assertEqual(manifest["summary"]["ok"], 0)
        self.assertEqual(manifest["summary"]["failed"], 1)
        self.assertEqual(len(manifest["errors"]), 1)
        self.assertEqual(manifest["errors"][0]["code"], "VIDEO_UNAVAILABLE")

    def test_process_channel_max_errors(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="any",
            subtitle_format="srt",
            output_dir=self.out_dir,
            max_errors=2,
        )
        adapter = FakeChannelVideoAdapter(
            entries=CHANNEL_ENTRIES[:4],
            raise_error={
                "abc12345678": YtcapError(ErrorCode.VIDEO_UNAVAILABLE, "Video 1 is unavailable", exit_code=3),
                "xyz98765432": YtcapError(ErrorCode.VIDEO_UNAVAILABLE, "Video 2 is unavailable", exit_code=3),
            },
        )

        with self.assertRaises(YtcapError) as context:
            process_channel(options, adapter=adapter)

        self.assertEqual(context.exception.code, ErrorCode.YTDLP_FAILED)
        self.assertIn("processing aborted after reaching 2 errors", context.exception.message)

        manifest_files = list((self.out_dir / "runs").glob("*.manifest.json"))
        self.assertEqual(len(manifest_files), 1)
        with open(manifest_files[0], "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["summary"]["total"], 4)
        self.assertEqual(manifest["summary"]["ok"], 0)
        self.assertEqual(manifest["summary"]["failed"], 2)
        self.assertEqual(len(manifest["errors"]), 2)

    def test_process_channel_ignore_no_subs(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="manual",
            subtitle_format="srt",
            output_dir=self.out_dir,
            ignore_no_subs=True,
        )
        adapter = FakeChannelVideoAdapter(
            entries=CHANNEL_ENTRIES[:3],
            raise_error={
                "abc12345678": YtcapError(ErrorCode.SUBTITLE_NOT_FOUND, "Subtitle not found", exit_code=4),
                "xyz98765432": YtcapError(ErrorCode.VIDEO_UNAVAILABLE, "Video is unavailable", exit_code=3),
            },
        )

        result = process_channel(options, adapter=adapter)

        # 3 total:
        # - abc12345678 fails with SUBTITLE_NOT_FOUND -> ignored/skipped because ignore_no_subs=True
        # - xyz98765432 fails with VIDEO_UNAVAILABLE -> failed
        # - def55511122 succeeds -> ok
        self.assertEqual(result.total, 3)
        self.assertEqual(result.ok, 1)
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.failed, 1)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["ok"], 1)
        self.assertEqual(manifest["summary"]["skipped"], 1)
        self.assertEqual(manifest["summary"]["failed"], 1)
        # Errors should only list VIDEO_UNAVAILABLE, not SUBTITLE_NOT_FOUND
        self.assertEqual(len(manifest["errors"]), 1)
        self.assertEqual(manifest["errors"][0]["video_id"], "xyz98765432")
        self.assertEqual(manifest["errors"][0]["code"], "VIDEO_UNAVAILABLE")

    def test_process_channel_without_ignore_no_subs_fails_on_missing_subs(self) -> None:
        options = ProcessChannelOptions(
            url="https://www.youtube.com/channel/UCabc123",
            language="en",
            source="manual",
            subtitle_format="srt",
            output_dir=self.out_dir,
            ignore_no_subs=False,
        )
        adapter = FakeChannelVideoAdapter(
            entries=CHANNEL_ENTRIES[:1],
            raise_error=YtcapError(ErrorCode.SUBTITLE_NOT_FOUND, "Subtitle not found", exit_code=4),
        )

        result = process_channel(options, adapter=adapter)

        self.assertEqual(result.total, 1)
        self.assertEqual(result.ok, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.failed, 1)

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["summary"]["ok"], 0)
        self.assertEqual(manifest["summary"]["failed"], 1)
        self.assertEqual(len(manifest["errors"]), 1)
        self.assertEqual(manifest["errors"][0]["code"], "SUBTITLE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
