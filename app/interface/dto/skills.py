"""Compatibility re-export for skill API DTOs."""

from app.interface.dto.skills_discovery import SkillDiscoveryRequest, SkillDiscoveryResponse
from app.interface.dto.skills_fetch import (
    SkillVersionListResponse,
    SkillVersionMetadataResponse,
    SkillVersionSummaryResponse,
)
from app.interface.dto.skills_lifecycle import (
    SkillVersionStatusResponse,
    SkillVersionStatusUpdateRequest,
)
from app.interface.dto.skills_publish import (
    DependencySelectorRequest,
    ExactRelationshipSelectorRequest,
    ProvenanceRequest,
    SkillGovernanceRequest,
    SkillVersionCreateRequest,
    SkillVersionMetadataRequest,
    SkillVersionRelationshipsRequest,
)
from app.interface.dto.skills_resolution import (
    DependencySelectorResponse,
    SkillDependencyResolutionResponse,
)
from app.interface.dto.skills_shared import (
    ChecksumResponse,
    ProvenanceResponse,
    SkillContentSummaryResponse,
    SkillMetadataResponse,
    TrustContextResponse,
)

__all__ = [
    "ChecksumResponse",
    "DependencySelectorRequest",
    "DependencySelectorResponse",
    "ExactRelationshipSelectorRequest",
    "ProvenanceRequest",
    "ProvenanceResponse",
    "SkillContentSummaryResponse",
    "SkillDependencyResolutionResponse",
    "SkillDiscoveryRequest",
    "SkillDiscoveryResponse",
    "SkillGovernanceRequest",
    "SkillMetadataResponse",
    "SkillVersionCreateRequest",
    "SkillVersionListResponse",
    "SkillVersionMetadataRequest",
    "SkillVersionMetadataResponse",
    "SkillVersionRelationshipsRequest",
    "SkillVersionStatusResponse",
    "SkillVersionStatusUpdateRequest",
    "SkillVersionSummaryResponse",
    "TrustContextResponse",
]
