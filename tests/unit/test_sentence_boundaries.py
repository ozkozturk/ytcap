"""Sentence boundary detection tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ytcap.services.sentence_boundaries import (  # noqa: E402
    BOUNDARY_ENGINE,
    GAP_STRONG_SIGNAL_SECONDS,
    GAP_WEAK_SIGNAL_SECONDS,
    JunctionHint,
    classify_cue_gap,
    find_sentence_spans,
)


def span_texts(text: str, hints: list[JunctionHint] | None = None) -> list[str]:
    return [span.text for span in find_sentence_spans(text, hints or [])]


class SentenceBoundaryTest(unittest.TestCase):
    def test_basic_terminal_punctuation(self) -> None:
        self.assertEqual(
            span_texts("Hello world. Are you ready? Yes!"),
            ["Hello world.", "Are you ready?", "Yes!"],
        )

    def test_keeps_trailing_unpunctuated_text(self) -> None:
        self.assertEqual(
            span_texts("Hello world. unfinished thought"),
            ["Hello world.", "unfinished thought"],
        )

    def test_closing_double_quote_stays_inside_sentence(self) -> None:
        self.assertEqual(
            span_texts('He said, "I don\'t know."'),
            ['He said, "I don\'t know."'],
        )

    def test_closing_quote_after_terminal_before_next_sentence(self) -> None:
        self.assertEqual(
            span_texts('She answered "No." He left.'),
            ['She answered "No."', "He left."],
        )

    def test_closing_brackets_stay_inside_sentence(self) -> None:
        self.assertEqual(
            span_texts("It worked (surprisingly well!). Then it broke."),
            ["It worked (surprisingly well!).", "Then it broke."],
        )

    def test_common_abbreviations_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("Dr. Smith arrived. Mr. Brown agreed."),
            ["Dr. Smith arrived.", "Mr. Brown agreed."],
        )

    def test_more_abbreviations_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("Mrs. Jones met Prof. Adams and Sr. Lopez. They left."),
            ["Mrs. Jones met Prof. Adams and Sr. Lopez.", "They left."],
        )

    def test_etc_and_eg_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("We use e.g. Node.js and React.js, etc. in class."),
            ["We use e.g. Node.js and React.js, etc. in class."],
        )

    def test_decimal_numbers_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("The value is 3.14. It is not 10.5 exactly."),
            ["The value is 3.14.", "It is not 10.5 exactly."],
        )

    def test_version_numbers_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("We use v2.4.1 today. Node 22.5 works too."),
            ["We use v2.4.1 today.", "Node 22.5 works too."],
        )

    def test_domains_and_technical_names_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("Node.js works well. Visit example.com. Next.js is a framework."),
            ["Node.js works well.", "Visit example.com.", "Next.js is a framework."],
        )

    def test_react_js_does_not_split(self) -> None:
        self.assertEqual(
            span_texts("React.js renders fast. It is popular."),
            ["React.js renders fast.", "It is popular."],
        )

    def test_initials_do_not_split(self) -> None:
        self.assertEqual(
            span_texts("J. R. R. Tolkien wrote it. Many read it."),
            ["J. R. R. Tolkien wrote it.", "Many read it."],
        )

    def test_dotted_acronym_does_not_split(self) -> None:
        self.assertEqual(
            span_texts("The U.S. government responded. It was quick."),
            ["The U.S. government responded.", "It was quick."],
        )

    def test_ellipsis_splits_deterministically(self) -> None:
        self.assertEqual(
            span_texts("Well... I don't know."),
            ["Well...", "I don't know."],
        )

    def test_ellipsis_character_splits_deterministically(self) -> None:
        self.assertEqual(
            span_texts("Well… I don't know."),
            ["Well…", "I don't know."],
        )

    def test_leading_ellipsis_produces_no_punctuation_only_sentence(self) -> None:
        self.assertEqual(
            span_texts("...than here. And none of us can say boo."),
            ["than here.", "And none of us can say boo."],
        )

    def test_exclamation_question_runs_count_once(self) -> None:
        self.assertEqual(
            span_texts("Really?! Yes!"),
            ["Really?!", "Yes!"],
        )

    def test_empty_and_whitespace_text(self) -> None:
        self.assertEqual(span_texts(""), [])
        self.assertEqual(span_texts("   "), [])

    def test_boundary_engine_name_is_stable(self) -> None:
        self.assertEqual(BOUNDARY_ENGINE, "punctuation-v2")


class CueGapClassificationTest(unittest.TestCase):
    def test_gap_thresholds(self) -> None:
        self.assertEqual(GAP_WEAK_SIGNAL_SECONDS, 0.20)
        self.assertEqual(GAP_STRONG_SIGNAL_SECONDS, 0.60)

    def test_classify_cue_gap(self) -> None:
        self.assertEqual(classify_cue_gap(0.10), "none")
        self.assertEqual(classify_cue_gap(0.20), "weak")
        self.assertEqual(classify_cue_gap(0.45), "weak")
        self.assertEqual(classify_cue_gap(0.60), "strong")
        self.assertEqual(classify_cue_gap(1.20), "strong")

    def test_negative_gap_is_none(self) -> None:
        self.assertEqual(classify_cue_gap(-0.5), "none")


class JunctionHintTest(unittest.TestCase):
    def test_strong_gap_with_uppercase_splits_unpunctuated_text(self) -> None:
        text = "and then he said I don't know. Next one."
        hints = [JunctionHint(offset=16, gap_seconds=0.9, next_starts_uppercase=True)]
        self.assertEqual(
            span_texts(text, hints),
            ["and then he said", "I don't know.", "Next one."],
        )

    def test_strong_gap_with_lowercase_does_not_split(self) -> None:
        text = "and none of us can say boo."
        hints = [JunctionHint(offset=14, gap_seconds=0.9, next_starts_uppercase=False)]
        self.assertEqual(span_texts(text, hints), ["and none of us can say boo."])

    def test_weak_gap_does_not_split(self) -> None:
        text = "and then he said I don't know."
        hints = [JunctionHint(offset=16, gap_seconds=0.4, next_starts_uppercase=True)]
        self.assertEqual(span_texts(text, hints), ["and then he said I don't know."])

    def test_gap_never_splits_well_punctuated_continuing_sentence(self) -> None:
        text = "...than here. And none of us can say boo."
        hints = [JunctionHint(offset=27, gap_seconds=1.5, next_starts_uppercase=False)]
        self.assertEqual(
            span_texts(text, hints),
            ["than here.", "And none of us can say boo."],
        )

    def test_junction_inside_word_is_ignored(self) -> None:
        text = "and then he said I don't know."
        hints = [JunctionHint(offset=5, gap_seconds=0.9, next_starts_uppercase=True)]
        self.assertEqual(span_texts(text, hints), ["and then he said I don't know."])

    def test_junction_at_existing_terminal_boundary_is_deduplicated(self) -> None:
        text = "Hello world. How are you."
        # Offset 12 is the space right after the terminal boundary "Hello world."
        hints = [JunctionHint(offset=12, gap_seconds=0.9, next_starts_uppercase=True)]
        self.assertEqual(span_texts(text, hints), ["Hello world.", "How are you."])


if __name__ == "__main__":
    unittest.main()
