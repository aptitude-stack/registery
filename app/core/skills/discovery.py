"""Core discovery service for ordered candidate slug retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.governance import CallerIdentity

from .models import SkillCoordinate
from .search import SkillSearchQuery, SkillSearchService


@dataclass(frozen=True, slots=True)
class SkillDiscoveryRequest:
    """Body-based discovery request for candidate slug lookup."""

    query: str
    tags: tuple[str, ...]
    context_skills: tuple[SkillCoordinate, ...] = ()


class SkillDiscoveryService(SkillSearchService):
    """Discovery facade that narrows search output to ordered candidate slugs."""

    def discover_candidates(
        self,
        *,
        caller: CallerIdentity,
        request: SkillDiscoveryRequest,
    ) -> tuple[str, ...]:
        """Return ordered candidate slugs for the provided discovery request."""
        results = self.search(
            caller=caller,
            query=SkillSearchQuery(
                q=request.query,
                tags=request.tags,
                language=None,
                fresh_within_days=None,
                max_footprint_bytes=None,
                limit=20,
                context_skills=tuple(
                    dict.fromkeys(coordinate.slug for coordinate in request.context_skills)
                ),
                semantic_text=request.query,
                semantic_text_is_explicit=True,
            ),
        )
        return tuple(item.slug for item in results)
