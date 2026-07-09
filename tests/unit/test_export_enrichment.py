"""Export enrichment model tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.models.export_enrichment import export_enrichment_fields, normalize_dataset_category  # noqa: E402


def sample_metadata() -> dict[str, object]:
    return {
        "video": {
            "title": "Example Video",
            "url": "https://www.youtube.com/watch?v=abc123",
            "webpage_url": "https://www.youtube.com/watch?v=abc123",
            "duration_seconds": 320,
            "upload_date": "20260101",
        },
        "channel": {
            "id": "channel123",
            "name": "Example Channel",
            "url": "https://www.youtube.com/channel/channel123",
        },
        "subtitles": [
            {"language": "en", "source": "manual", "downloaded": True},
            {"language": "en-GB", "source": "manual", "downloaded": False},
            {"language": "tr", "source": "manual", "downloaded": False},
            {"language": "de", "source": "manual", "downloaded": False},
            {"language": "tr", "source": "manual", "downloaded": True},
            {"language": "de", "source": "auto", "downloaded": True},
        ],
    }


class ExportEnrichmentTest(unittest.TestCase):
    def test_export_enrichment_fields_maps_metadata(self) -> None:
        fields = export_enrichment_fields(sample_metadata())

        self.assertEqual(fields["channel_id"], "channel123")
        self.assertEqual(fields["channel_name"], "Example Channel")
        self.assertEqual(fields["video_title"], "Example Video")
        self.assertEqual(fields["video_duration_seconds"], 320)
        self.assertEqual(fields["available_manual_subtitles"], ["de", "tr"])
        self.assertEqual(fields["downloaded_subtitles"], ["de", "tr"])
        self.assertIsNone(fields["dataset_category"])
        self.assertEqual(fields["category_source"], "none")

    def test_export_enrichment_fields_uses_nulls_for_missing_metadata(self) -> None:
        fields = export_enrichment_fields({"schema_version": "0.1"})

        self.assertIsNone(fields["channel_id"])
        self.assertIsNone(fields["channel_name"])
        self.assertIsNone(fields["video_title"])
        self.assertIsNone(fields["available_manual_subtitles"])
        self.assertIsNone(fields["downloaded_subtitles"])

    def test_export_enrichment_fields_adds_user_category(self) -> None:
        fields = export_enrichment_fields(sample_metadata(), category="education")

        self.assertEqual(fields["dataset_category"], "education")
        self.assertEqual(fields["category_source"], "user")

    def test_normalize_dataset_category_strips_value(self) -> None:
        self.assertEqual(normalize_dataset_category(" education "), "education")

    def test_normalize_dataset_category_rejects_empty_value(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            normalize_dataset_category("  ")

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("--category must not be empty", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
