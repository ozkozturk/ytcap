"""Subtitle format validation tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.services.subtitle_format import SUPPORTED_SUBTITLE_FORMATS, validate_subtitle_format  # noqa: E402


class SubtitleFormatTest(unittest.TestCase):
    def test_supported_formats_are_srt_and_vtt(self) -> None:
        self.assertEqual(SUPPORTED_SUBTITLE_FORMATS, ("srt", "vtt"))

    def test_validate_subtitle_format_accepts_supported_formats(self) -> None:
        self.assertEqual(validate_subtitle_format("srt"), "srt")
        self.assertEqual(validate_subtitle_format("vtt"), "vtt")

    def test_validate_subtitle_format_rejects_unsupported_format(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            validate_subtitle_format("json")

        self.assertEqual(raised.exception.code, ErrorCode.UNSUPPORTED_FORMAT)
        self.assertEqual(raised.exception.exit_code, 2)
        self.assertIn("supported formats: srt, vtt", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
