"""Video metadata normalization tests."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.models.video_metadata import inspect_payload, normalize_video_metadata  # noqa: E402


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class VideoMetadataTest(unittest.TestCase):
    def test_normalize_video_metadata_maps_stable_fields(self) -> None:
        raw = json.loads((FIXTURE_DIR / "sample.info.json").read_text(encoding="utf-8"))

        metadata = normalize_video_metadata(raw, fetched_at=datetime(2026, 7, 6, 20, 0, tzinfo=UTC))

        self.assertEqual(metadata["schema_version"], "0.1")
        self.assertEqual(metadata["video"]["id"], "abc123")
        self.assertEqual(metadata["video"]["duration_seconds"], 320)
        self.assertEqual(metadata["channel"]["name"], "Example Channel")
        self.assertEqual(metadata["media"]["tags"], ["example", "video"])
        self.assertEqual(metadata["extraction"]["fetched_at"], "2026-07-06T20:00:00Z")

    def test_normalize_video_metadata_maps_subtitle_tracks(self) -> None:
        raw = json.loads((FIXTURE_DIR / "sample.info.json").read_text(encoding="utf-8"))

        metadata = normalize_video_metadata(raw, fetched_at=datetime(2026, 7, 6, 20, 0, tzinfo=UTC))

        tracks = {(item["language"], item["source"]): item for item in metadata["subtitles"]}
        self.assertEqual(tracks[("en", "manual")]["formats"], ["srt", "vtt"])
        self.assertEqual(tracks[("en", "auto")]["formats"], ["vtt"])
        self.assertEqual(tracks[("tr", "auto")]["formats"], ["vtt"])
        self.assertFalse(tracks[("en", "manual")]["selected"])
        self.assertIsNone(tracks[("en", "manual")]["path"])

    def test_inspect_payload_uses_summary_shape(self) -> None:
        raw = json.loads((FIXTURE_DIR / "sample.info.json").read_text(encoding="utf-8"))
        metadata = normalize_video_metadata(raw, fetched_at=datetime(2026, 7, 6, 20, 0, tzinfo=UTC))

        payload = inspect_payload(metadata)

        self.assertEqual(payload["video_id"], "abc123")
        self.assertEqual(payload["title"], "Example Video")
        self.assertIn({"language": "en", "source": "manual", "formats": ["srt", "vtt"]}, payload["subtitles"])


if __name__ == "__main__":
    unittest.main()
