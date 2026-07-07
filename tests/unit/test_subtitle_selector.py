"""Subtitle source selection tests."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.services.subtitle_selector import select_subtitle_track  # noqa: E402


def sample_tracks() -> list[dict[str, object]]:
    return [
        {
            "language": "en",
            "source": "manual",
            "formats": ["srt", "vtt"],
            "selected": False,
            "downloaded": False,
            "path": None,
        },
        {
            "language": "en",
            "source": "auto",
            "formats": ["vtt"],
            "selected": False,
            "downloaded": False,
            "path": None,
        },
        {
            "language": "tr",
            "source": "auto",
            "formats": ["vtt"],
            "selected": False,
            "downloaded": False,
            "path": None,
        },
    ]


class SubtitleSelectorTest(unittest.TestCase):
    def test_manual_selection_chooses_manual_track(self) -> None:
        selected = select_subtitle_track(
            sample_tracks(),
            language="en",
            source="manual",
            subtitle_format="srt",
        )

        self.assertEqual(selected["language"], "en")
        self.assertEqual(selected["source"], "manual")
        self.assertTrue(selected["selected"])

    def test_manual_selection_does_not_fall_back_to_auto(self) -> None:
        tracks = [sample_tracks()[1]]

        with self.assertRaises(YtcapError) as raised:
            select_subtitle_track(tracks, language="en", source="manual", subtitle_format="vtt")

        self.assertEqual(raised.exception.code, ErrorCode.SUBTITLE_NOT_FOUND)
        self.assertEqual(raised.exception.exit_code, 4)

    def test_manual_selection_accepts_english_language_variants(self) -> None:
        tracks = [
            {
                "language": "en-GB",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "en-eEY6OEpapP",
                "source": "manual",
                "formats": ["vtt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
        ]

        selected_srt = select_subtitle_track(tracks, language="en", source="manual", subtitle_format="srt")
        selected_vtt = select_subtitle_track(tracks, language="en", source="manual", subtitle_format="vtt")

        self.assertEqual(selected_srt["language"], "en-GB")
        self.assertEqual(selected_srt["source"], "manual")
        self.assertTrue(selected_srt["selected"])
        self.assertEqual(selected_vtt["language"], "en-eEY6OEpapP")

    def test_multiple_manual_english_variants_choose_first_normalized_track(self) -> None:
        tracks = [
            {
                "language": "en-GB",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "en-USA",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "en-abc123",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
        ]

        selected = select_subtitle_track(tracks, language="en", source="manual", subtitle_format="srt")

        self.assertEqual(selected["language"], "en-GB")
        self.assertEqual(selected["source"], "manual")
        self.assertTrue(selected["selected"])

    def test_exact_english_language_is_preferred_over_variant(self) -> None:
        tracks = [
            {
                "language": "en-GB",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "en",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
        ]

        selected = select_subtitle_track(tracks, language="en", source="manual", subtitle_format="srt")

        self.assertEqual(selected["language"], "en")

    def test_any_selection_prefers_manual_english_variant_over_auto_exact(self) -> None:
        tracks = [
            {
                "language": "en",
                "source": "auto",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "en-GB",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
        ]

        selected = select_subtitle_track(tracks, language="en", source="any", subtitle_format="srt")

        self.assertEqual(selected["language"], "en-GB")
        self.assertEqual(selected["source"], "manual")

    def test_english_variant_matching_does_not_accept_unrelated_codes(self) -> None:
        tracks = [
            {
                "language": "en_US",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "english",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
            {
                "language": "sen",
                "source": "manual",
                "formats": ["srt"],
                "selected": False,
                "downloaded": False,
                "path": None,
            },
        ]

        with self.assertRaises(YtcapError) as raised:
            select_subtitle_track(tracks, language="en", source="manual", subtitle_format="srt")

        self.assertEqual(raised.exception.code, ErrorCode.SUBTITLE_NOT_FOUND)

    def test_auto_selection_chooses_auto_track(self) -> None:
        selected = select_subtitle_track(
            sample_tracks(),
            language="en",
            source="auto",
            subtitle_format="vtt",
        )

        self.assertEqual(selected["language"], "en")
        self.assertEqual(selected["source"], "auto")
        self.assertTrue(selected["selected"])

    def test_any_selection_prefers_manual_track(self) -> None:
        selected = select_subtitle_track(
            sample_tracks(),
            language="en",
            source="any",
            subtitle_format="vtt",
        )

        self.assertEqual(selected["source"], "manual")

    def test_any_selection_falls_back_to_auto_track(self) -> None:
        tracks = [sample_tracks()[1]]

        selected = select_subtitle_track(tracks, language="en", source="any", subtitle_format="vtt")

        self.assertEqual(selected["source"], "auto")
        self.assertTrue(selected["selected"])

    def test_missing_language_source_or_format_raises_subtitle_not_found(self) -> None:
        cases = [
            {"language": "de", "source": "any", "subtitle_format": "vtt"},
            {"language": "tr", "source": "manual", "subtitle_format": "vtt"},
            {"language": "en", "source": "auto", "subtitle_format": "srt"},
        ]

        for case in cases:
            with self.subTest(case=case), self.assertRaises(YtcapError) as raised:
                select_subtitle_track(sample_tracks(), **case)

            self.assertEqual(raised.exception.code, ErrorCode.SUBTITLE_NOT_FOUND)
            self.assertEqual(raised.exception.exit_code, 4)
            self.assertIsNotNone(raised.exception.details)
            self.assertEqual(raised.exception.details.get("language"), case["language"])
            self.assertEqual(raised.exception.details.get("source"), case["source"])
            self.assertEqual(raised.exception.details.get("format"), case["subtitle_format"])

    def test_unsupported_format_raises_unsupported_format(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            select_subtitle_track(sample_tracks(), language="en", source="manual", subtitle_format="json")

        self.assertEqual(raised.exception.code, ErrorCode.UNSUPPORTED_FORMAT)
        self.assertEqual(raised.exception.exit_code, 2)

    def test_selection_returns_copy_without_mutating_tracks(self) -> None:
        tracks = sample_tracks()
        original = deepcopy(tracks)

        selected = select_subtitle_track(tracks, language="en", source="any", subtitle_format="vtt")

        self.assertIsNot(selected, tracks[0])
        self.assertEqual(tracks, original)
        self.assertFalse(tracks[0]["selected"])
        self.assertTrue(selected["selected"])


if __name__ == "__main__":
    unittest.main()
