"""Text normalization helpers."""

from __future__ import annotations

import unicodedata


APOSTROPHE_CHARACTERS = frozenset({"'", "`", "´", "ʼ", "‘", "’", "＇"})


def normalize_search_text(text: str) -> str:
    """Normalize display text into a compact search-friendly form."""

    normalized = unicodedata.normalize("NFKD", text)
    output: list[str] = []
    for character in normalized:
        if unicodedata.combining(character):
            continue
        for folded in character.casefold():
            if folded in APOSTROPHE_CHARACTERS:
                continue
            if _is_search_character(folded):
                output.append(folded)
            else:
                output.append(" ")
    return " ".join("".join(output).split())


def _is_search_character(character: str) -> bool:
    category = unicodedata.category(character)
    return category.startswith("L") or category.startswith("N")
