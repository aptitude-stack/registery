"""Shared HTTP contract validation constants and helpers."""

from __future__ import annotations

import re

from .skill_bundle import (
    MAX_SKILL_BUNDLE_FILE_COUNT,
    MAX_SKILL_BUNDLE_PATH_LENGTH,
    MAX_SKILL_BUNDLE_SIZE_BYTES,
    SkillBundleValidationError,
    SkillBundleValidationReport,
    validate_skill_bundle,
)

SEMVER_CORE = (
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
SEMVER_PATTERN = rf"^{SEMVER_CORE}$"
SLUG_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$"
VERSION_CONSTRAINT_PATTERN = re.compile(
    rf"^\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*"
    rf"(?:,\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*)*$"
)
MARKER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")

__all__ = [
    "MARKER_PATTERN",
    "MAX_SKILL_BUNDLE_FILE_COUNT",
    "MAX_SKILL_BUNDLE_PATH_LENGTH",
    "MAX_SKILL_BUNDLE_SIZE_BYTES",
    "SEMVER_CORE",
    "SEMVER_PATTERN",
    "SLUG_PATTERN",
    "SkillBundleValidationError",
    "SkillBundleValidationReport",
    "VERSION_CONSTRAINT_PATTERN",
    "validate_skill_bundle",
]
