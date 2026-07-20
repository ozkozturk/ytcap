"""Subtitle sentence segmentation orchestration.

The segmentation pipeline keeps four responsibilities separate:

1. Sentence boundary detection: :func:`find_sentence_spans` decides which
   character offsets start and end a sentence inside the joined timeline
   text.
2. Cue-to-time mapping: each cue keeps its global character span, so a
   sentence span maps back to the cues it touches.
3. Timestamp estimation: :func:`estimate_cue_offset_seconds` places
   cue-internal boundaries on the time axis with weighted token interpolation.
4. Playback range: :func:`playback_range` pads the estimated sentence times
   into a safe playback interval.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ytcap.models.subtitle import SubtitleCue, SubtitleSentence
from ytcap.services.sentence_boundaries import (
    BOUNDARY_ENGINE,
    CLOSING_CHARACTERS,
    TERMINAL_RUN_CHARACTERS,
    JunctionHint,
    SentenceSpan,
    find_sentence_spans,
)
from ytcap.services.sentence_timing import (
    estimate_cue_offset_seconds,
    playback_range,
    quantize_time,
)


@dataclass(frozen=True)
class _CueTextSpan:
    cue: SubtitleCue
    start: int
    end: int


def split_sentences(text: str) -> list[str]:
    """Split text into sentences with the dependency-free boundary detector."""

    normalized_text = _normalize_text(text)
    if not normalized_text:
        return []
    return [span.text for span in find_sentence_spans(normalized_text)]


def segment_cues_into_sentences(cues: Sequence[SubtitleCue]) -> list[SubtitleSentence]:
    normalized_text, cue_spans = _build_timeline_text(cues)
    if not normalized_text:
        return []

    junction_hints = _junction_hints(normalized_text, cue_spans)
    sentences: list[SubtitleSentence] = []
    previous_end_seconds = 0.0
    for sentence_index, span in enumerate(
        find_sentence_spans(normalized_text, junction_hints),
        start=1,
    ):
        touched_spans = _overlapping_spans(cue_spans, span.start, span.end)
        if not touched_spans:
            continue

        start_seconds = _boundary_seconds(touched_spans[0], span.start, normalized_text)
        end_seconds = _boundary_seconds(touched_spans[-1], span.end, normalized_text)
        start_seconds = max(start_seconds, previous_end_seconds)
        end_seconds = max(end_seconds, start_seconds)
        previous_end_seconds = end_seconds

        start_seconds = quantize_time(start_seconds)
        end_seconds = quantize_time(end_seconds)
        playback_start, playback_end = playback_range(start_seconds, end_seconds)

        cue_coverage = "single" if len(touched_spans) == 1 else "multiple"
        timing_precision = _timing_precision(span, touched_spans)
        sentences.append(
            SubtitleSentence(
                index=sentence_index,
                start=start_seconds,
                end=end_seconds,
                text=span.text,
                timing_strategy=_legacy_timing_strategy(cue_coverage, timing_precision),
                playback_start=quantize_time(playback_start),
                playback_end=quantize_time(playback_end),
                cue_coverage=cue_coverage,
                timing_precision=timing_precision,
                start_cue_index=touched_spans[0].cue.index,
                end_cue_index=touched_spans[-1].cue.index,
                cue_count=len(touched_spans),
                start_char_in_first_cue=span.start - touched_spans[0].start,
                end_char_in_last_cue=span.end - touched_spans[-1].start,
                boundary_engine=BOUNDARY_ENGINE,
            )
        )
    return sentences


def _build_timeline_text(cues: Sequence[SubtitleCue]) -> tuple[str, list[_CueTextSpan]]:
    text_parts: list[str] = []
    cue_spans: list[_CueTextSpan] = []
    offset = 0

    for cue in cues:
        cue_text = _normalize_text(cue.text)
        if not cue_text:
            continue
        if text_parts:
            text_parts.append(" ")
            offset += 1
        text_parts.append(cue_text)
        cue_spans.append(_CueTextSpan(cue=cue, start=offset, end=offset + len(cue_text)))
        offset += len(cue_text)

    return "".join(text_parts), cue_spans


def _junction_hints(text: str, cue_spans: Sequence[_CueTextSpan]) -> list[JunctionHint]:
    hints: list[JunctionHint] = []
    for current, following in zip(cue_spans, cue_spans[1:]):
        hints.append(
            JunctionHint(
                offset=current.end,
                gap_seconds=following.cue.start - current.cue.end,
                next_starts_uppercase=_starts_with_uppercase(
                    text[following.start : following.end]
                ),
            )
        )
    return hints


def _starts_with_uppercase(text: str) -> bool:
    for character in text:
        if character.isalpha():
            return character.isupper()
    return False


def _overlapping_spans(
    cue_spans: Sequence[_CueTextSpan],
    start: int,
    end: int,
) -> list[_CueTextSpan]:
    return [span for span in cue_spans if span.start < end and span.end > start]


def _boundary_seconds(span: _CueTextSpan, offset: int, timeline_text: str) -> float:
    cue_text = timeline_text[span.start : span.end]
    return estimate_cue_offset_seconds(span.cue, cue_text, offset - span.start)


def _timing_precision(span: SentenceSpan, touched_spans: Sequence[_CueTextSpan]) -> str:
    if not _ends_with_terminal(span.text):
        return "unknown"
    start_aligned = span.start == touched_spans[0].start
    end_aligned = span.end == touched_spans[-1].end
    if start_aligned and end_aligned:
        return "cue_aligned"
    if start_aligned:
        return "estimated_end"
    if end_aligned:
        return "estimated_start"
    return "estimated_both"


def _ends_with_terminal(text: str) -> bool:
    index = len(text) - 1
    while index >= 0 and text[index] in CLOSING_CHARACTERS:
        index -= 1
    return index >= 0 and text[index] in TERMINAL_RUN_CHARACTERS


def _legacy_timing_strategy(cue_coverage: str, timing_precision: str) -> str:
    """Derive the backward-compatible ``timing_strategy`` value."""

    if timing_precision == "unknown":
        return "unknown"
    if cue_coverage == "multiple":
        return "cue_merge"
    if timing_precision == "cue_aligned":
        return "cue_exact"
    return "heuristic"


def _normalize_text(text: str) -> str:
    return " ".join(text.split())
