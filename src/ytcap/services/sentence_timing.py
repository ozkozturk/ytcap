"""Cue-internal timestamp estimation and playback range helpers.

The primary estimator uses *weighted token interpolation*: each token in a
cue text receives an approximate speaking-time weight (longer words and
punctuation pauses weigh more), and a character offset inside the cue is
mapped to a time by the ratio of cumulative weight before the offset to the
total cue weight.

These weights are rough heuristics, not measured speaking durations. When
weighted estimation is not possible, a character-ratio fallback is used.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ytcap.models.subtitle import SubtitleCue


WORD_BASE_WEIGHT = 1.0
WORD_LENGTH_WEIGHT = 0.35
WORD_LENGTH_CAP = 12
COMMA_PAUSE_WEIGHT = 0.20
CLAUSE_PAUSE_WEIGHT = 0.35
TERMINAL_PAUSE_WEIGHT = 0.55

PLAYBACK_START_PADDING_SECONDS = 0.25
PLAYBACK_END_PADDING_SECONDS = 0.40

TIME_QUANTUM_DECIMALS = 3  # millisecond precision

QUOTE_BRACKET_CHARACTERS = "\"'“”‘’()[]{}"
WORD_RE = r"\w+(?:[.'’]\w+)*"
TOKEN_RE = re.compile(
    r"[.!?…]+"  # terminal punctuation run
    + r"|[,;:]"  # comma, semicolon, or colon pause
    + r"|" + WORD_RE  # word, including contractions and dotted names
    + r"|[" + re.escape(QUOTE_BRACKET_CHARACTERS) + r"]+"  # standalone quotes/brackets
    + r"|\S"  # any other single non-space character
)


@dataclass(frozen=True)
class _WeightedToken:
    start: int
    end: int
    weight: float


def estimate_cue_offset_seconds(
    cue: SubtitleCue,
    cue_text: str,
    char_offset: int,
) -> float:
    """Estimate the time of ``char_offset`` inside ``cue``.

    ``cue_text`` must be the normalized cue text used for the timeline so
    offsets stay consistent. Falls back to character-ratio interpolation when
    no weighted tokens are available, and to ``cue.start`` for zero-duration
    cues.
    """

    duration = cue.end - cue.start
    if duration <= 0 or not cue_text:
        return cue.start

    clamped_offset = min(max(char_offset, 0), len(cue_text))
    if clamped_offset <= 0:
        return cue.start
    if clamped_offset >= len(cue_text):
        return cue.end

    tokens = _weighted_tokens(cue_text)
    total_weight = sum(token.weight for token in tokens)
    if total_weight <= 0:
        return _character_ratio_seconds(cue, len(cue_text), clamped_offset)

    cumulative_weight = _cumulative_weight_before(tokens, clamped_offset)
    ratio = cumulative_weight / total_weight
    estimated = cue.start + duration * ratio
    return min(max(estimated, cue.start), cue.end)


def playback_range(start: float, end: float) -> tuple[float, float]:
    """Apply safety padding around a sentence's estimated time range.

    ``playback_end`` is intentionally not clipped to a video duration because
    the video duration is not known at segmentation time.
    """

    playback_start = max(0.0, start - PLAYBACK_START_PADDING_SECONDS)
    playback_end = end + PLAYBACK_END_PADDING_SECONDS
    return playback_start, playback_end


def quantize_time(seconds: float) -> float:
    """Round a time value to ``TIME_QUANTUM_DECIMALS`` precision."""

    return round(seconds, TIME_QUANTUM_DECIMALS)


def _weighted_tokens(cue_text: str) -> list[_WeightedToken]:
    return [
        _WeightedToken(start=match.start(), end=match.end(), weight=_token_weight(match.group()))
        for match in TOKEN_RE.finditer(cue_text)
    ]


def _token_weight(token: str) -> float:
    first = token[0]
    if first in ".!?…":
        return TERMINAL_PAUSE_WEIGHT
    if first == ",":
        return COMMA_PAUSE_WEIGHT
    if first in ";:":
        return CLAUSE_PAUSE_WEIGHT
    if first in QUOTE_BRACKET_CHARACTERS:
        return 0.0
    letter_count = sum(1 for character in token if character.isalnum())
    capped_length = min(letter_count, WORD_LENGTH_CAP)
    return WORD_BASE_WEIGHT + WORD_LENGTH_WEIGHT * math.sqrt(capped_length)


def _cumulative_weight_before(tokens: list[_WeightedToken], char_offset: int) -> float:
    cumulative = 0.0
    for token in tokens:
        if token.end <= char_offset:
            cumulative += token.weight
        elif token.start >= char_offset:
            break
        else:
            covered = char_offset - token.start
            cumulative += token.weight * covered / (token.end - token.start)
    return cumulative


def _character_ratio_seconds(cue: SubtitleCue, cue_length: int, char_offset: int) -> float:
    if cue_length <= 0:
        return cue.start
    ratio = char_offset / cue_length
    return cue.start + (cue.end - cue.start) * ratio
