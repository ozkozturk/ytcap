"""Subtitle data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SubtitleCue:
    index: int | None
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, int | float | str | None]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
        }


@dataclass(frozen=True)
class SubtitleSentence:
    """A sentence derived from one or more subtitle cues.

    ``start``/``end`` are the estimated semantic sentence boundaries, while
    ``playback_start``/``playback_end`` are the padded playback range. The
    ``start_char_in_first_cue``/``end_char_in_last_cue`` offsets are relative
    to the normalized cue text used during segmentation.
    """

    index: int
    start: float
    end: float
    text: str
    timing_strategy: str
    playback_start: float
    playback_end: float
    cue_coverage: str
    timing_precision: str
    start_cue_index: int | None
    end_cue_index: int | None
    cue_count: int
    start_char_in_first_cue: int
    end_char_in_last_cue: int
    boundary_engine: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "timing_strategy": self.timing_strategy,
            "playback_start": self.playback_start,
            "playback_end": self.playback_end,
            "cue_coverage": self.cue_coverage,
            "timing_precision": self.timing_precision,
            "start_cue_index": self.start_cue_index,
            "end_cue_index": self.end_cue_index,
            "cue_count": self.cue_count,
            "start_char_in_first_cue": self.start_char_in_first_cue,
            "end_char_in_last_cue": self.end_char_in_last_cue,
            "boundary_engine": self.boundary_engine,
        }
