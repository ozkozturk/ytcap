"""Dependency-free sentence boundary detection.

The detector scans text for terminal punctuation candidates and decides with
small, readable rules whether each candidate really ends a sentence. It never
uses NLP packages; every rule is deterministic and documented.

Known limitations (by design, kept deterministic):

- Abbreviations such as ``Mr.`` or ``etc.`` are never treated as sentence
  endings, so a sentence that truly ends with one merges with the next
  sentence.
- Dotted acronyms such as ``U.S.`` are never treated as sentence endings for
  the same reason.
- An ellipsis (``...`` or ``…``) is always terminal, so ``Well... I don't
  know.`` deterministically becomes two sentences.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


BOUNDARY_ENGINE = "punctuation-v2"

TERMINAL_RUN_CHARACTERS = frozenset({".", "!", "?", "…"})
NON_DOT_TERMINALS = frozenset({"!", "?", "…"})
CLOSING_CHARACTERS = frozenset({'"', "'", "”", "’", ")", "]", "}"})

GAP_WEAK_SIGNAL_SECONDS = 0.20
GAP_STRONG_SIGNAL_SECONDS = 0.60

ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "e.g",
        "i.e",
        "etc",
        "vs",
    }
)

DOTTED_ACRONYM_RE = re.compile(r"(?:[A-Za-z]\.)+[A-Za-z]")


@dataclass(frozen=True)
class SentenceSpan:
    """A sentence located by character offsets inside a timeline text."""

    start: int
    end: int
    text: str


@dataclass(frozen=True)
class JunctionHint:
    """Auxiliary boundary signal at the junction between two subtitle cues."""

    offset: int
    gap_seconds: float
    next_starts_uppercase: bool


def classify_cue_gap(gap_seconds: float) -> str:
    """Classify the silence gap between two consecutive cues.

    The gap is only an auxiliary signal; punctuation always takes priority
    over it when deciding sentence boundaries.
    """

    if gap_seconds < GAP_WEAK_SIGNAL_SECONDS:
        return "none"
    if gap_seconds < GAP_STRONG_SIGNAL_SECONDS:
        return "weak"
    return "strong"


def find_sentence_spans(
    text: str,
    junction_hints: Sequence[JunctionHint] = (),
) -> list[SentenceSpan]:
    """Find sentence spans in ``text``.

    ``junction_hints`` describe cue junctions inside the text. A junction only
    becomes a boundary when the cue gap is strong and the next cue starts with
    an uppercase letter, so a well punctuated continuing sentence is never
    split just because of a cue gap.
    """

    if not text.strip():
        return []
    boundaries = _terminal_boundaries(text)
    boundaries.extend(_junction_boundaries(text, boundaries, junction_hints))
    return _spans_from_boundaries(text, boundaries)


def _terminal_boundaries(text: str) -> list[int]:
    boundaries: list[int] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] in TERMINAL_RUN_CHARACTERS:
            run_end = index + 1
            while run_end < length and text[run_end] in TERMINAL_RUN_CHARACTERS:
                run_end += 1
            if _is_terminal_run(text, index, text[index:run_end]):
                boundaries.append(_absorb_closers(text, run_end))
            index = run_end
        else:
            index += 1
    return boundaries


def _is_terminal_run(text: str, run_start: int, run: str) -> bool:
    if any(character in NON_DOT_TERMINALS for character in run):
        return True
    if len(run) >= 2:
        return True  # ellipsis such as "..."
    return _is_dot_terminal(text, run_start)


def _is_dot_terminal(text: str, dot_index: int) -> bool:
    before = text[dot_index - 1] if dot_index > 0 else ""
    after = text[dot_index + 1] if dot_index + 1 < len(text) else ""
    if before.isalnum() and after.isalnum():
        # Dot inside a number, version, domain, or technical name:
        # 3.14, v2.4.1, example.com, Node.js, U.S.
        return False

    token = _token_before_dot(text, dot_index)
    if not token:
        return True
    if token.lower() in ABBREVIATIONS:
        return False
    if len(token) == 1 and token.isalpha():
        return False  # single-letter initial such as "J." in "J. R. R. Tolkien"
    if DOTTED_ACRONYM_RE.fullmatch(token):
        return False  # dotted acronym such as "U.S." or "e.g."
    return True


def _token_before_dot(text: str, dot_index: int) -> str:
    index = dot_index - 1
    while index >= 0 and (text[index].isalnum() or text[index] == "."):
        index -= 1
    return text[index + 1 : dot_index]


def _absorb_closers(text: str, index: int) -> int:
    """Extend a boundary through closing characters and further terminals.

    A sentence such as ``(surprisingly well!).`` ends only after the final
    dot, so closing brackets and any immediately following terminal run all
    belong to the same boundary.
    """

    while index < len(text):
        if text[index] in CLOSING_CHARACTERS or text[index] in TERMINAL_RUN_CHARACTERS:
            index += 1
        else:
            break
    return index


def _junction_boundaries(
    text: str,
    terminal_boundaries: Sequence[int],
    junction_hints: Sequence[JunctionHint],
) -> list[int]:
    boundaries: list[int] = []
    for hint in junction_hints:
        if hint.offset <= 0 or hint.offset >= len(text):
            continue
        if not text[hint.offset].isspace():
            continue  # junctions must sit on the space between cue texts
        if classify_cue_gap(hint.gap_seconds) != "strong":
            continue
        if not hint.next_starts_uppercase:
            continue
        if _near_existing_boundary(terminal_boundaries, hint.offset):
            continue
        if _near_existing_boundary(boundaries, hint.offset):
            continue
        boundaries.append(hint.offset)
    return boundaries


def _near_existing_boundary(boundaries: Sequence[int], offset: int) -> bool:
    return any(abs(boundary - offset) <= 1 for boundary in boundaries)


def _spans_from_boundaries(text: str, boundaries: Sequence[int]) -> list[SentenceSpan]:
    spans: list[SentenceSpan] = []
    start = 0
    for boundary in sorted(set(boundaries)):
        if boundary <= start:
            continue
        span = _make_span(text, start, boundary)
        if span is not None:
            spans.append(span)
        start = boundary
    tail = _make_span(text, start, len(text))
    if tail is not None:
        spans.append(tail)
    return spans


def _make_span(text: str, start: int, end: int) -> SentenceSpan | None:
    start, end = _trim_offsets(text, start, end)
    if start >= end:
        return None
    segment = text[start:end]
    if not any(character.isalnum() for character in segment):
        return None  # punctuation-only fragment such as a leading "..."
    return SentenceSpan(start=start, end=end, text=segment)


def _trim_offsets(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
