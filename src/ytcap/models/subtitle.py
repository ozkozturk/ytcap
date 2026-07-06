"""Subtitle data models."""

from __future__ import annotations

from dataclasses import dataclass


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

