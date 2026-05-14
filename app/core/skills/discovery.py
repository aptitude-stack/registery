"""Core discovery service for ordered candidate slug retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.governance import CallerIdentity
from app.intelligence.discovery_signals import build_semantic_query_source

from .search import SkillSearchQuery, SkillSearchService


@dataclass(frozen=True, slots=True)
class SkillDiscoveryRequest:
    """Body-based discovery request for candidate slug lookup."""

    name: str
    description: str | None
    tags: tuple[str, ...]
    context_skills: tuple[str, ...] = ()


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
                q=_query_text(request),
                tags=request.tags,
                language=None,
                fresh_within_days=None,
                max_footprint_bytes=None,
                limit=20,
                context_skills=request.context_skills,
                semantic_text=build_semantic_query_source(
                    description=request.description,
                    tags=request.tags,
                ),
                semantic_text_is_explicit=True,
            ),
        )
        return tuple(item.slug for item in results)


def _query_text(request: SkillDiscoveryRequest) -> str:
    parts = [request.name]
    if request.description:
        parts.append(request.description)
    return " ".join(parts)
