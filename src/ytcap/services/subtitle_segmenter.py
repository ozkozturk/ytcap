"""Subtitle sentence segmentation helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ytcap.models.subtitle import SubtitleCue, SubtitleSentence


SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$")
TERMINAL_PUNCTUATION = ".!?"


@dataclass(frozen=True)
class _CueTextSpan:
    cue: SubtitleCue
    start: int
    end: int


def split_sentences(text: str) -> list[str]:
    """Split text using a small punctuation-based heuristic."""

    normalized_text = _normalize_text(text)
    if not normalized_text:
        return []
    return [sentence for sentence, _, _ in _sentence_spans(normalized_text)]


def segment_cues_into_sentences(cues: Sequence[SubtitleCue]) -> list[SubtitleSentence]:
    normalized_text, cue_spans = _build_timeline_text(cues)
    if not normalized_text:
        return []

    sentences: list[SubtitleSentence] = []
    for sentence_index, (sentence_text, start_offset, end_offset) in enumerate(
        _sentence_spans(normalized_text),
        start=1,
    ):
        touched_spans = _overlapping_spans(cue_spans, start_offset, end_offset)
        if not touched_spans:
            continue

        start_seconds = _seconds_for_offset(touched_spans[0], start_offset)
        end_seconds = _seconds_for_offset(touched_spans[-1], end_offset)
        sentences.append(
            SubtitleSentence(
                index=sentence_index,
                start=start_seconds,
                end=end_seconds,
                text=sentence_text,
                timing_strategy=_timing_strategy(
                    sentence_text,
                    touched_spans,
                    start_offset,
                    end_offset,
                ),
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


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for match in SENTENCE_RE.finditer(text):
        start, end = _trim_span(text, match.start(), match.end())
        if start >= end:
            continue
        spans.append((text[start:end], start, end))
    return spans


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _overlapping_spans(
    cue_spans: Sequence[_CueTextSpan],
    start: int,
    end: int,
) -> list[_CueTextSpan]:
    return [span for span in cue_spans if span.start < end and span.end > start]


def _seconds_for_offset(span: _CueTextSpan, offset: int) -> float:
    cue_length = span.end - span.start
    if cue_length <= 0:
        return span.cue.start

    relative_offset = min(max(offset - span.start, 0), cue_length)
    ratio = relative_offset / cue_length
    return span.cue.start + ((span.cue.end - span.cue.start) * ratio)


def _timing_strategy(
    sentence_text: str,
    touched_spans: Sequence[_CueTextSpan],
    start_offset: int,
    end_offset: int,
) -> str:
    if not sentence_text.endswith(tuple(TERMINAL_PUNCTUATION)):
        return "unknown"
    if len(touched_spans) > 1:
        return "cue_merge"

    span = touched_spans[0]
    if start_offset == span.start and end_offset == span.end:
        return "cue_exact"
    return "heuristic"


def _normalize_text(text: str) -> str:
    return " ".join(text.split())
