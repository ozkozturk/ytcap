"""Batch parser tests."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError
from ytcap.services.batch_parser import parse_batch_content, parse_batch_file


class BatchParserTest(unittest.TestCase):
    def test_parse_empty_content(self) -> None:
        self.assertEqual(parse_batch_content(""), [])
        self.assertEqual(parse_batch_content("   \n   \n"), [])

    def test_parse_comments_only(self) -> None:
        content = (
            "# This is a comment\n"
            "  # Another comment with leading whitespace\n"
            "\n"
            "# More comments\n"
        )
        self.assertEqual(parse_batch_content(content), [])

    def test_parse_video_ids(self) -> None:
        content = (
            "dQw4w9WgXcQ\n"
            "jNQXAC9IVRw  \n"
            "  dQw4w9WgXcQ\n"
        )
        sources = parse_batch_content(content)
        self.assertEqual(len(sources), 3)
        self.assertEqual(sources[0].video_id, "dQw4w9WgXcQ")
        self.assertIsNone(sources[0].url)
        self.assertEqual(sources[1].video_id, "jNQXAC9IVRw")
        self.assertEqual(sources[2].video_id, "dQw4w9WgXcQ")

    def test_parse_video_urls(self) -> None:
        content = (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
            "http://youtu.be/jNQXAC9IVRw\n"
        )
        sources = parse_batch_content(content)
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0].url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertIsNone(sources[0].video_id)
        self.assertEqual(sources[1].url, "http://youtu.be/jNQXAC9IVRw")

    def test_parse_inline_comments(self) -> None:
        content = (
            "dQw4w9WgXcQ # Rick Astley\n"
            "https://www.youtube.com/watch?v=jNQXAC9IVRw   # Another video URL\n"
            "  # Just a comment\n"
        )
        sources = parse_batch_content(content)
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0].video_id, "dQw4w9WgXcQ")
        self.assertEqual(sources[1].url, "https://www.youtube.com/watch?v=jNQXAC9IVRw")

    def test_parse_file_success(self) -> None:
        content = (
            "# Batch list\n"
            "dQw4w9WgXcQ\n"
            "https://youtu.be/jNQXAC9IVRw # inline comment\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "videos.txt"
            file_path.write_text(content, encoding="utf-8")
            
            sources = parse_batch_file(file_path)
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[0].video_id, "dQw4w9WgXcQ")
            self.assertEqual(sources[1].url, "https://youtu.be/jNQXAC9IVRw")

    def test_parse_file_missing_raises_error(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            parse_batch_file("non_existent_file_path.txt")
        
        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertEqual(raised.exception.exit_code, 2)
        self.assertIn("could not read batch file", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
