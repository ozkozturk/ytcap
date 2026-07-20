"""Weighted token interpolation and playback range tests."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.models.subtitle import SubtitleCue  # noqa: E402
from ytcap.services.sentence_timing import (  # noqa: E402
    CLAUSE_PAUSE_WEIGHT,
    COMMA_PAUSE_WEIGHT,
    PLAYBACK_END_PADDING_SECONDS,
    PLAYBACK_START_PADDING_SECONDS,
    TERMINAL_PAUSE_WEIGHT,
    WORD_BASE_WEIGHT,
    WORD_LENGTH_CAP,
    WORD_LENGTH_WEIGHT,
    _token_weight,
    _weighted_tokens,
    estimate_cue_offset_seconds,
    playback_range,
    quantize_time,
)


class TokenWeightTest(unittest.TestCase):
    def test_word_weight_grows_with_letter_count(self) -> None:
        short = _token_weight("go")
        medium = _token_weight("hello")
        long = _token_weight("internationalization")

        self.assertGreater(medium, short)
        self.assertGreater(long, medium)
        self.assertAlmostEqual(short, WORD_BASE_WEIGHT + WORD_LENGTH_WEIGHT * math.sqrt(2))

    def test_word_weight_is_capped(self) -> None:
        capped = WORD_BASE_WEIGHT + WORD_LENGTH_WEIGHT * math.sqrt(WORD_LENGTH_CAP)
        self.assertAlmostEqual(_token_weight("a" * 30), capped)

    def test_punctuation_weights(self) -> None:
        self.assertEqual(_token_weight(","), COMMA_PAUSE_WEIGHT)
        self.assertEqual(_token_weight(";"), CLAUSE_PAUSE_WEIGHT)
        self.assertEqual(_token_weight(":"), CLAUSE_PAUSE_WEIGHT)
        self.assertEqual(_token_weight("."), TERMINAL_PAUSE_WEIGHT)
        self.assertEqual(_token_weight("..."), TERMINAL_PAUSE_WEIGHT)
        self.assertEqual(_token_weight("?"), TERMINAL_PAUSE_WEIGHT)

    def test_quotes_and_brackets_have_zero_weight(self) -> None:
        for token in ('"', "'", "”", "’", ")", "]", "}", "(", "[", "{"):
            self.assertEqual(_token_weight(token), 0.0)

    def test_contractions_and_dotted_names_are_single_tokens(self) -> None:
        cue_text = "don't Node.js v2.4.1"
        tokens = _weighted_tokens(cue_text)
        token_texts = [cue_text[token.start : token.end] for token in tokens]
        self.assertIn("don't", token_texts)
        self.assertIn("Node.js", token_texts)
        self.assertIn("v2.4.1", token_texts)


class EstimateCueOffsetTest(unittest.TestCase):
    def test_offset_at_start_and_end_returns_cue_bounds(self) -> None:
        cue = SubtitleCue(index=1, start=2.0, end=6.0, text="Hello world.")
        self.assertEqual(estimate_cue_offset_seconds(cue, "Hello world.", 0), 2.0)
        self.assertEqual(estimate_cue_offset_seconds(cue, "Hello world.", len("Hello world.")), 6.0)

    def test_offset_is_clamped_to_cue_bounds(self) -> None:
        cue = SubtitleCue(index=1, start=2.0, end=6.0, text="Hello world.")
        self.assertEqual(estimate_cue_offset_seconds(cue, "Hello world.", -5), 2.0)
        self.assertEqual(estimate_cue_offset_seconds(cue, "Hello world.", 999), 6.0)

    def test_weighted_estimate_differs_from_character_ratio(self) -> None:
        cue = SubtitleCue(index=1, start=0.0, end=10.0, text="...than here. And none of us")
        cue_text = "...than here. And none of us"
        and_offset = cue_text.index("And")

        weighted = estimate_cue_offset_seconds(cue, cue_text, and_offset)
        char_ratio = 10.0 * and_offset / len(cue_text)

        self.assertNotAlmostEqual(weighted, char_ratio, places=2)
        # Punctuation pause weights pull the estimate earlier than char ratio.
        self.assertLess(weighted, char_ratio)
        self.assertGreater(weighted, 0.0)

    def test_estimate_stays_within_cue_time_bounds(self) -> None:
        cue = SubtitleCue(index=1, start=5.0, end=9.0, text="One two three four five.")
        cue_text = "One two three four five."
        for offset in range(len(cue_text) + 1):
            estimated = estimate_cue_offset_seconds(cue, cue_text, offset)
            self.assertGreaterEqual(estimated, 5.0)
            self.assertLessEqual(estimated, 9.0)

    def test_zero_duration_cue_returns_cue_start(self) -> None:
        cue = SubtitleCue(index=1, start=3.0, end=3.0, text="Hello.")
        self.assertEqual(estimate_cue_offset_seconds(cue, "Hello.", 3), 3.0)

    def test_empty_cue_text_returns_cue_start(self) -> None:
        cue = SubtitleCue(index=1, start=3.0, end=4.0, text="")
        self.assertEqual(estimate_cue_offset_seconds(cue, "", 0), 3.0)

    def test_zero_total_weight_falls_back_to_character_ratio(self) -> None:
        cue = SubtitleCue(index=1, start=0.0, end=10.0, text='"""')
        estimated = estimate_cue_offset_seconds(cue, '"""', 1)
        self.assertAlmostEqual(estimated, 10.0 / 3)


class PlaybackRangeTest(unittest.TestCase):
    def test_padding_defaults(self) -> None:
        self.assertEqual(PLAYBACK_START_PADDING_SECONDS, 0.25)
        self.assertEqual(PLAYBACK_END_PADDING_SECONDS, 0.40)

    def test_playback_range_applies_padding(self) -> None:
        start, end = playback_range(10.0, 12.0)
        self.assertAlmostEqual(start, 9.75)
        self.assertAlmostEqual(end, 12.4)

    def test_playback_start_never_goes_negative(self) -> None:
        start, _ = playback_range(0.1, 1.0)
        self.assertEqual(start, 0.0)

    def test_playback_invariant_holds(self) -> None:
        for start, end in ((0.0, 0.0), (0.1, 0.1), (5.0, 9.0), (0.0, 3.0)):
            playback_start, playback_end = playback_range(start, end)
            self.assertLessEqual(playback_start, start)
            self.assertLessEqual(start, end)
            self.assertLessEqual(end, playback_end)

    def test_playback_end_is_not_clipped_without_video_duration(self) -> None:
        _, playback_end = playback_range(100.0, 200.0)
        self.assertAlmostEqual(playback_end, 200.4)


class QuantizeTimeTest(unittest.TestCase):
    def test_millisecond_rounding(self) -> None:
        self.assertEqual(quantize_time(18.400000000000002), 18.4)
        self.assertEqual(quantize_time(1.0), 1.0)
        self.assertEqual(quantize_time(11.6666666), 11.667)


if __name__ == "__main__":
    unittest.main()
