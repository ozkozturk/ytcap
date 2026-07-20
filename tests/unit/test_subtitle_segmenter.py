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


class SplitSentencesTest(unittest.TestCase):
    def test_split_sentences_uses_basic_terminal_punctuation(self) -> None:
        sentences = split_sentences("Hello world. Are you ready? Yes!")

        self.assertEqual(sentences, ["Hello world.", "Are you ready?", "Yes!"])

    def test_split_sentences_keeps_trailing_unpunctuated_text(self) -> None:
        sentences = split_sentences("Hello world. unfinished thought")

        self.assertEqual(sentences, ["Hello world.", "unfinished thought"])

    def test_split_sentences_keeps_closing_quote_inside_sentence(self) -> None:
        sentences = split_sentences('He said, "I don\'t know."')

        self.assertEqual(sentences, ['He said, "I don\'t know."'])


class SegmentCuesTest(unittest.TestCase):
    def test_segment_single_complete_cue_as_cue_aligned(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=1.0, end=3.5, text="Hello world.")]
        )

        self.assertEqual(len(sentences), 1)
        sentence = sentences[0]
        self.assertEqual(sentence.text, "Hello world.")
        self.assertEqual(sentence.start, 1.0)
        self.assertEqual(sentence.end, 3.5)
        self.assertEqual(sentence.cue_coverage, "single")
        self.assertEqual(sentence.timing_precision, "cue_aligned")
        self.assertEqual(sentence.timing_strategy, "cue_exact")
        self.assertEqual(sentence.cue_count, 1)
        self.assertEqual(sentence.start_cue_index, 1)
        self.assertEqual(sentence.end_cue_index, 1)

    def test_single_cue_playback_padding(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=1.0, end=3.5, text="Hello world.")]
        )

        sentence = sentences[0]
        self.assertAlmostEqual(sentence.playback_start, 0.75)
        self.assertAlmostEqual(sentence.playback_end, 3.9)
        self.assertLessEqual(sentence.playback_start, sentence.start)
        self.assertLessEqual(sentence.end, sentence.playback_end)

    def test_playback_start_never_goes_negative(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=0.1, end=2.0, text="Hello.")]
        )

        self.assertEqual(sentences[0].playback_start, 0.0)

    def test_segment_sentence_across_cues(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=1.0, end=2.0, text="Hello"),
                SubtitleCue(index=2, start=2.5, end=4.0, text="world."),
            ]
        )

        self.assertEqual(len(sentences), 1)
        sentence = sentences[0]
        self.assertEqual(sentence.text, "Hello world.")
        self.assertEqual(sentence.start, 1.0)
        self.assertEqual(sentence.end, 4.0)
        self.assertEqual(sentence.cue_coverage, "multiple")
        self.assertEqual(sentence.timing_precision, "cue_aligned")
        self.assertEqual(sentence.timing_strategy, "cue_merge")
        self.assertEqual(sentence.cue_count, 2)
        self.assertEqual(sentence.start_cue_index, 1)
        self.assertEqual(sentence.end_cue_index, 2)

    def test_segment_sentence_across_three_cues(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=2.0, text="First part"),
                SubtitleCue(index=2, start=2.0, end=4.0, text="of the long"),
                SubtitleCue(index=3, start=4.0, end=6.0, text="sentence here."),
            ]
        )

        self.assertEqual(len(sentences), 1)
        sentence = sentences[0]
        self.assertEqual(sentence.text, "First part of the long sentence here.")
        self.assertEqual(sentence.cue_count, 3)
        self.assertEqual(sentence.cue_coverage, "multiple")
        self.assertEqual(sentence.start_cue_index, 1)
        self.assertEqual(sentence.end_cue_index, 3)

    def test_two_sentences_inside_one_cue(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=0.0, end=10.0, text="Hello. Goodbye!")]
        )

        self.assertEqual([sentence.text for sentence in sentences], ["Hello.", "Goodbye!"])
        self.assertEqual(
            [sentence.timing_strategy for sentence in sentences],
            ["heuristic", "heuristic"],
        )
        self.assertEqual(sentences[0].timing_precision, "estimated_end")
        self.assertEqual(sentences[1].timing_precision, "estimated_start")

        self.assertEqual(sentences[0].start, 0.0)
        self.assertGreater(sentences[0].end, sentences[0].start)
        self.assertGreaterEqual(sentences[1].start, sentences[0].end)
        self.assertEqual(sentences[1].end, 10.0)

        # The two sentences must not reuse the full cue range identically.
        full_range = (0.0, 10.0)
        self.assertNotEqual((sentences[0].start, sentences[0].end), full_range)
        self.assertNotEqual((sentences[1].start, sentences[1].end), full_range)

    def test_sentence_starting_mid_cue_uses_weighted_estimate(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=10.0, end=14.0, text="...than here. And none of us"),
                SubtitleCue(
                    index=2,
                    start=14.2,
                    end=18.0,
                    text='can say "Boo," because none of us have ever been to prison.',
                ),
            ]
        )

        self.assertEqual(len(sentences), 2)
        sentence = sentences[1]
        self.assertEqual(
            sentence.text,
            'And none of us can say "Boo," because none of us have ever been to prison.',
        )
        # The start must not fall back to the cue start; it is estimated near "And".
        self.assertGreater(sentence.start, 10.5)
        self.assertLess(sentence.start, 13.5)
        self.assertEqual(sentence.end, 18.0)
        self.assertEqual(sentence.cue_coverage, "multiple")
        self.assertEqual(sentence.timing_precision, "estimated_start")
        self.assertEqual(sentence.start_cue_index, 1)
        self.assertEqual(sentence.end_cue_index, 2)
        # Char offset of "And" inside the normalized first cue text.
        self.assertEqual(sentence.start_char_in_first_cue, 14)

    def test_segment_unpunctuated_cue_marks_timing_unknown(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=1.0, end=2.0, text="No terminal punctuation")]
        )

        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "No terminal punctuation")
        self.assertEqual(sentences[0].timing_precision, "unknown")
        self.assertEqual(sentences[0].timing_strategy, "unknown")

    def test_zero_duration_cue_is_safe(self) -> None:
        sentences = segment_cues_into_sentences(
            [SubtitleCue(index=1, start=3.0, end=3.0, text="Hello.")]
        )

        self.assertEqual(len(sentences), 1)
        sentence = sentences[0]
        self.assertEqual(sentence.start, 3.0)
        self.assertEqual(sentence.end, 3.0)
        self.assertGreaterEqual(sentence.playback_end, sentence.end)

    def test_empty_and_whitespace_cues_are_ignored(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=1.0, text="   "),
                SubtitleCue(index=2, start=1.0, end=2.0, text=""),
                SubtitleCue(index=3, start=2.0, end=4.0, text="Hello world."),
            ]
        )

        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "Hello world.")
        self.assertEqual(sentences[0].start_cue_index, 3)
        self.assertEqual(sentences[0].cue_count, 1)

    def test_empty_input_returns_no_sentences(self) -> None:
        self.assertEqual(segment_cues_into_sentences([]), [])

    def test_sentence_times_are_monotonic(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=3.0, text="One. Two."),
                SubtitleCue(index=2, start=3.2, end=6.0, text="Three. Four."),
                SubtitleCue(index=3, start=6.2, end=9.0, text="Five. Six."),
            ]
        )

        previous_end = 0.0
        for sentence in sentences:
            self.assertGreaterEqual(sentence.start, previous_end)
            self.assertGreaterEqual(sentence.end, sentence.start)
            self.assertLessEqual(sentence.playback_start, sentence.start)
            self.assertLessEqual(sentence.end, sentence.playback_end)
            previous_end = sentence.end

    def test_overlapping_source_cues_preserve_overlapping_sentence_times(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=5.0, text="One."),
                SubtitleCue(index=2, start=2.0, end=4.0, text="Two."),
            ]
        )

        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0].end, 5.0)
        self.assertEqual(sentences[1].start, 2.0)
        self.assertLess(sentences[1].start, sentences[0].end)

    def test_strong_gap_splits_unpunctuated_uppercase_continuation(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=2.0, text="and then he said"),
                SubtitleCue(index=2, start=3.0, end=5.0, text="I don't know."),
            ]
        )

        self.assertEqual(
            [sentence.text for sentence in sentences],
            ["and then he said", "I don't know."],
        )
        self.assertEqual(sentences[1].start, 3.0)
        self.assertEqual(sentences[1].timing_precision, "cue_aligned")

    def test_gap_does_not_split_lowercase_continuation(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=2.0, text="and none of us"),
                SubtitleCue(index=2, start=3.5, end=5.0, text="can say boo."),
            ]
        )

        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "and none of us can say boo.")

    def test_provenance_fields_are_populated(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=7, start=10.0, end=14.0, text="...than here. And none of us"),
                SubtitleCue(index=8, start=14.2, end=18.0, text="can say boo."),
            ]
        )

        sentence = sentences[1]
        self.assertEqual(sentence.start_cue_index, 7)
        self.assertEqual(sentence.end_cue_index, 8)
        self.assertEqual(sentence.cue_count, 2)
        self.assertEqual(sentence.start_char_in_first_cue, 14)
        self.assertEqual(sentence.end_char_in_last_cue, len("can say boo."))
        self.assertEqual(sentence.boundary_engine, "punctuation-v2")

    def test_abbreviations_and_technical_names_stay_in_one_sentence(self) -> None:
        sentences = segment_cues_into_sentences(
            [
                SubtitleCue(index=1, start=0.0, end=3.0, text="Dr. Smith explained Node.js today."),
            ]
        )

        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "Dr. Smith explained Node.js today.")
        self.assertEqual(sentences[0].timing_precision, "cue_aligned")


class SubtitleSentenceModelTest(unittest.TestCase):
    def test_subtitle_sentence_converts_to_dict(self) -> None:
        sentence = SubtitleSentence(
            index=1,
            start=1.0,
            end=2.5,
            text="Hello.",
            timing_strategy="cue_exact",
            playback_start=0.75,
            playback_end=2.9,
            cue_coverage="single",
            timing_precision="cue_aligned",
            start_cue_index=1,
            end_cue_index=1,
            cue_count=1,
            start_char_in_first_cue=0,
            end_char_in_last_cue=6,
            boundary_engine="punctuation-v2",
        )

        self.assertEqual(
            sentence.to_dict(),
            {
                "index": 1,
                "start": 1.0,
                "end": 2.5,
                "text": "Hello.",
                "timing_strategy": "cue_exact",
                "playback_start": 0.75,
                "playback_end": 2.9,
                "cue_coverage": "single",
                "timing_precision": "cue_aligned",
                "start_cue_index": 1,
                "end_cue_index": 1,
                "cue_count": 1,
                "start_char_in_first_cue": 0,
                "end_char_in_last_cue": 6,
                "boundary_engine": "punctuation-v2",
            },
        )


if __name__ == "__main__":
    unittest.main()
