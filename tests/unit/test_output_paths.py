"""Output path helper tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.exporters.output_paths import (  # noqa: E402
    OUTPUT_DIRECTORIES,
    build_output_layout,
    ensure_output_layout,
    normalized_file_path,
    safe_filename_part,
)


class OutputPathsTest(unittest.TestCase):
    def test_build_output_layout_returns_stable_paths(self) -> None:
        layout = build_output_layout(Path("data"))

        self.assertEqual(layout.metadata_path("abc123"), Path("data/videos/abc123.info.json"))
        self.assertEqual(
            layout.subtitle_path("abc123", "en", "manual", "srt"),
            Path("data/subtitles/abc123.en.manual.srt"),
        )
        self.assertEqual(layout.normalized_path("abc123", "en", "cue"), Path("data/normalized/abc123.en.cue.jsonl"))
        self.assertEqual(
            layout.run_manifest_path("2026-07-06T20-00-00Z"),
            Path("data/runs/2026-07-06T20-00-00Z.manifest.json"),
        )
        self.assertEqual(layout.failed_path(), Path("data/failed/failed.jsonl"))

    def test_safe_filename_part_rejects_path_traversal_and_separators(self) -> None:
        invalid_values = ["../escape", "a/b", "a\\b", "", ".", "..", "bad\nname"]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(YtcapError) as raised:
                    safe_filename_part(value, field_name="video_id")

                self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
                self.assertEqual(raised.exception.exit_code, 2)

    def test_layout_rejects_unsafe_dynamic_path_parts(self) -> None:
        layout = build_output_layout(Path("data"))

        with self.assertRaises(YtcapError):
            layout.metadata_path("../escape")
        with self.assertRaises(YtcapError):
            layout.subtitle_path("abc123", "en/us", "manual", "srt")
        with self.assertRaises(YtcapError):
            normalized_file_path(Path("data/normalized"), video_id="abc123", language=".", segments="cue")

    def test_ensure_output_layout_creates_expected_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "data"

            layout = ensure_output_layout(root)

            self.assertEqual(layout.root, root)
            for directory_name in OUTPUT_DIRECTORIES:
                self.assertTrue((root / directory_name).is_dir())

    def test_ensure_output_layout_wraps_directory_creation_errors(self) -> None:
        with patch("ytcap.exporters.output_paths.Path.mkdir", side_effect=OSError("permission denied")):
            with self.assertRaises(YtcapError) as raised:
                ensure_output_layout("data")

        self.assertEqual(raised.exception.code, ErrorCode.OUTPUT_WRITE_FAILED)
        self.assertEqual(raised.exception.exit_code, 5)


if __name__ == "__main__":
    unittest.main()
