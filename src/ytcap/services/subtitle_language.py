"""Subtitle language matching helpers."""

from __future__ import annotations

from typing import Any


def subtitle_language_match_rank(requested_language: str, candidate_language: Any) -> int | None:
    """Return a match rank for a subtitle language, or None when it does not match."""

    if not isinstance(candidate_language, str):
        return None
    if candidate_language == requested_language:
        return 0
    if requested_language == "en" and candidate_language.startswith("en-"):
        return 1
    return None
