"""Subtitle sentence segmentation tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.models.subtitle import SubtitleCue, SubtitleSentence  # noqa: E402
from ytcap.services.subtitle_segmenter import (  # noqa: E402
    segment_cues_into_sentences,
    split_sentences,
)


class SubtitleSegmenterTest(unittest.TestCase):
    def test_split_sentences_uses_basic_terminal_punctuation(self) -> None:
        sentences = split_sentences("Hello world. Are you ready? Yes!")

        self.assertEqual(sentences, ["Hello world.", "Are you ready?", "Yes!"])

    def test_split_sentences_keeps_trailing_unpunctuated_text(self) -> None:
        sentences = split_sentences("Hello world. unfinished thought")

        self.assertEqual(sentences, ["Hello world.", "unfinished thought"])

    def test_segment_single_complete_cue_as_exact_timing(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=1.0, end=3.5, text="Hello world.")]
        )

        self.assertEqual(
            sentences,
            [
                SubtitleSentence(
                    index=1,
                    start=1.0,
                    end=3.5,
                    text="Hello world.",
                    timing_strategy="cue_exact",
                )
            ],
        )

    def test_segment_multiple_sentences_inside_one_cue_uses_heuristic_timing(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=0.0, end=10.0, text="Hello. Goodbye!")]
        )

        self.assertEqual([sentence.text for sentence in sentences], ["Hello.", "Goodbye!"])
        self.assertEqual(
            [sentence.timing_strategy for sentence in sentences],
            ["heuristic", "heuristic"],
        )
        self.assertAlmostEqual(sentences[0].start, 0.0)
        self.assertGreater(sentences[0].end, sentences[0].start)
        self.assertGreater(sentences[1].start, sentences[0].end)
        self.assertAlmostEqual(sentences[1].end, 10.0)

    def test_segment_sentence_across_cues_uses_cue_merge_timing(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=1.0, end=2.0, text="Hello"),
                SubtitleCue(index=2, start=2.5, end=4.0, text="world."),
            ]
        )

        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "Hello world.")
        self.assertEqual(sentences[0].start, 1.0)
        self.assertEqual(sentences[0].end, 4.0)
        self.assertEqual(sentences[0].timing_strategy, "cue_merge")

    def test_segment_unpunctuated_cue_marks_timing_unknown(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=1.0, end=2.0, text="No terminal punctuation")]
        )

        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "No terminal punctuation")
        self.assertEqual(sentences[0].timing_strategy, "unknown")

    def test_subtitle_sentence_converts_to_dict(self) -> None:
        sentence = SubtitleSentence(
            index=1,
            start=1.0,
            end=2.5,
            text="Hello.",
            timing_strategy="cue_exact",
        )

        self.assertEqual(
            sentence.to_dict(),
            {
                "index": 1,
                "start": 1.0,
                "end": 2.5,
                "text": "Hello.",
                "timing_strategy": "cue_exact",
            },
        )


if __name__ == "__main__":
    unittest.main()
