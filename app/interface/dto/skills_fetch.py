"""Exact-fetch DTOs for skill APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.governance import LifecycleStatus, TrustTier
from app.interface.dto.skills_shared import (
    ChecksumResponse,
    ProvenanceResponse,
    SkillContentSummaryResponse,
    SkillMetadataResponse,
)


class SkillVersionMetadataResponse(BaseModel):
    """Exact metadata response returned by publish and exact metadata fetch."""

    slug: str
    version: str
    install_count: int
    version_checksum: ChecksumResponse
    content: SkillContentSummaryResponse
    metadata: SkillMetadataResponse
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    provenance: ProvenanceResponse | None = None
    published_at: datetime


class SkillVersionSummaryResponse(BaseModel):
    """Identity-level summary for one immutable version."""

    version: str
    lifecycle_status: LifecycleStatus
    trust_tier: TrustTier
    published_at: datetime
    is_current_default: bool


class SkillVersionListResponse(BaseModel):
    """Visible immutable versions for one skill identity."""

    slug: str
    versions: list[SkillVersionSummaryResponse]
