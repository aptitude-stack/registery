"""Shared normalization helpers for skill search and indexing."""

from __future__ import annotations

from collections.abc import Iterable

SEARCH_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "doc": ("documentation",),
    "docs": ("documentation",),
}


def normalize_search_text(value: str | None) -> str | None:
    """Normalize free-text input into a compact lowercase string."""
    if value is None:
        return None

    normalized = " ".join(value.split()).strip().lower()
    return normalized or None


def expand_search_aliases(value: str | None) -> str | None:
    """Expand bounded search aliases while preserving original token order."""
    normalized = normalize_search_text(value)
    if normalized is None:
        return None

    expanded: list[str] = []
    seen: set[str] = set()
    for token in normalized.split():
        for candidate in (token, *SEARCH_TOKEN_ALIASES.get(token, ())):
            if candidate not in seen:
                expanded.append(candidate)
                seen.add(candidate)
    return " ".join(expanded) or None


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
