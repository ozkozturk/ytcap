"""Metadata reader tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.errors import ErrorCode, YtcapError  # noqa: E402
from ytcap.services.metadata_reader import read_metadata_json  # noqa: E402


class MetadataReaderTest(unittest.TestCase):
    def test_read_metadata_json_returns_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "abc123.info.json"
            path.write_text(json.dumps({"schema_version": "0.1"}) + "\n", encoding="utf-8")

            self.assertEqual(read_metadata_json(path), {"schema_version": "0.1"})

    def test_read_metadata_json_missing_file_returns_invalid_input(self) -> None:
        with self.assertRaises(YtcapError) as raised:
            read_metadata_json("missing.info.json")

        self.assertEqual(raised.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn("metadata file not found", raised.exception.message)

    def test_read_metadata_json_invalid_json_returns_parse_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "abc123.info.json"
            path.write_text("{not json\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                read_metadata_json(path)

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertIn("could not parse metadata JSON", raised.exception.message)

    def test_read_metadata_json_non_object_returns_parse_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "abc123.info.json"
            path.write_text("[]\n", encoding="utf-8")

            with self.assertRaises(YtcapError) as raised:
                read_metadata_json(path)

        self.assertEqual(raised.exception.code, ErrorCode.PARSE_FAILED)
        self.assertIn("metadata JSON must be an object", raised.exception.message)


if __name__ == "__main__":
    unittest.main()
