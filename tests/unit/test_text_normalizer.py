"""Search text normalization tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.services.text_normalizer import normalize_search_text  # noqa: E402


class TextNormalizerTest(unittest.TestCase):
    def test_normalize_search_text_removes_apostrophes_and_punctuation(self) -> None:
        self.assertEqual(normalize_search_text("I can't wait;"), "i cant wait")

    def test_normalize_search_text_handles_unicode_case_and_accents(self) -> None:
        self.assertEqual(normalize_search_text("İstanbul'da CAFÉ!"), "istanbulda cafe")

    def test_normalize_search_text_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_search_text("One\n\n  two\tthree"), "one two three")


if __name__ == "__main__":
    unittest.main()
