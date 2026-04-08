"""SQLAlchemy adapter composed from port-aligned repository mixins."""

from __future__ import annotations

from app.core.ports import (
    SkillInstallCounterPort,
    SkillRegistryPort,
    SkillRelationshipReadPort,
    SkillSearchPort,
    SkillVersionReadPort,
)
from app.persistence.skill_registry_repository_base import SkillRegistryRepositoryBase
from app.persistence.skill_registry_repository_reads import SkillRegistryReadMixin
from app.persistence.skill_registry_repository_search import SkillRegistrySearchMixin
from app.persistence.skill_registry_repository_status import SkillRegistryStatusMixin
from app.persistence.skill_registry_repository_writes import SkillRegistryWriteMixin


class SQLAlchemySkillRegistryRepository(
    SkillRegistryWriteMixin,
    SkillRegistryReadMixin,
    SkillRegistrySearchMixin,
    SkillRegistryStatusMixin,
    SkillRegistryRepositoryBase,
    SkillRegistryPort,
    SkillVersionReadPort,
    SkillInstallCounterPort,
    SkillSearchPort,
    SkillRelationshipReadPort,
):
    """SQLAlchemy implementation for normalized immutable skill persistence."""
