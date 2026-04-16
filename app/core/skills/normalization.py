"""Shared normalization helpers for skill search and indexing."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_search_text(value: str | None) -> str | None:
    """Normalize free-text input into a compact lowercase string."""
    if value is None:
        return None

    normalized = " ".join(value.split()).strip().lower()
    return normalized or None


def normalize_tag(value: str | None) -> str | None:
    """Normalize a tag-like token for deterministic comparisons."""
    return normalize_search_text(value)


def normalize_tag_list(values: Iterable[str] | None) -> tuple[str, ...]:
    """Normalize, deduplicate, and deterministically order tag values."""
    if values is None:
        return ()

    normalized_values = {
        normalized for value in values if (normalized := normalize_tag(value)) is not None
    }
    return tuple(sorted(normalized_values))
