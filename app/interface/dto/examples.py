"""Shared request and response examples for the public API."""

from __future__ import annotations

PUBLISH_REQUEST_EXAMPLE = {
    "intent": "create_skill",
    "version": "1.2.3",
    "content": {
        "raw_markdown": "# Python Lint\n\nLint Python files consistently.\n",
    },
    "metadata": {
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"],
        "inputs_schema": {"type": "object"},
        "outputs_schema": {"type": "object"},
        "token_estimate": 128,
        "maturity_score": 0.9,
        "security_score": 0.95,
    },
    "governance": {
        "trust_tier": "internal",
        "provenance": {
            "repo_url": "https://github.com/example/skills",
            "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
            "tree_path": "skills/python.lint",
            "publisher_identity": "ci/acme-release",
        },
    },
    "relationships": {
        "depends_on": [
            {
                "slug": "python.base",
                "version_constraint": ">=1.0.0,<2.0.0",
                "optional": True,
                "markers": ["linux", "gpu"],
            }
        ],
        "extends": [{"slug": "python.base", "version": "1.0.0"}],
        "conflicts_with": [],
        "overlaps_with": [{"slug": "python.format", "version": "1.0.0"}],
    },
}

CHECKSUM_EXAMPLE = {
    "algorithm": "sha256",
    "digest": "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2",
}

SKILL_VERSION_METADATA_RESPONSE_EXAMPLE = {
    "slug": "python.lint",
    "version": "1.2.3",
    "install_count": 0,
    "version_checksum": CHECKSUM_EXAMPLE,
    "content": {
        "checksum": CHECKSUM_EXAMPLE,
        "size_bytes": 123,
    },
    "metadata": {
        "name": "Python Lint",
        "description": "Linting skill",
        "tags": ["python", "lint"],
        "inputs_schema": {"type": "object"},
        "outputs_schema": {"type": "object"},
        "token_estimate": 128,
        "maturity_score": 0.9,
        "security_score": 0.95,
    },
    "lifecycle_status": "published",
    "trust_tier": "internal",
    "provenance": {
        "repo_url": "https://github.com/example/skills",
        "commit_sha": "aabbccddeeff00112233445566778899aabbccdd",
        "tree_path": "skills/python.lint",
        "publisher_identity": "ci/acme-release",
        "trust_context": {
            "trust_tier": "internal",
            "policy_profile": "default",
        },
    },
    "published_at": "2026-03-10T08:30:00Z",
}

SKILL_VERSION_LIST_RESPONSE_EXAMPLE = {
    "slug": "python.lint",
    "versions": [
        {
            "version": "2.0.0",
            "lifecycle_status": "published",
            "trust_tier": "internal",
            "published_at": "2026-03-10T08:30:00Z",
            "is_current_default": True,
        },
        {
            "version": "1.2.3",
            "lifecycle_status": "deprecated",
            "trust_tier": "internal",
            "published_at": "2026-03-08T08:30:00Z",
            "is_current_default": False,
        },
    ],
}

DISCOVERY_REQUEST_EXAMPLE = {
    "name": "Python Lint",
    "description": "Lint Python files consistently",
    "tags": ["python", "lint"],
}

DISCOVERY_RESPONSE_EXAMPLE = {
    "candidates": [
        "python.lint",
        "python.format",
    ]
}

RESOLUTION_RESPONSE_EXAMPLE = {
    "slug": "python.lint",
    "version": "1.2.3",
    "depends_on": [
        {
            "slug": "python.base",
            "version_constraint": ">=1.0.0,<2.0.0",
            "optional": True,
            "markers": ["linux", "gpu"],
        }
    ],
}

INVALID_REQUEST_ERROR_EXAMPLE = {
    "error": {
        "code": "INVALID_REQUEST",
        "message": "Request validation failed.",
        "details": {
            "errors": [
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["path", "version"],
                    "msg": "String should match pattern",
                    "input": "latest",
                }
            ]
        },
    }
}

DUPLICATE_SKILL_VERSION_ERROR_EXAMPLE = {
    "error": {
        "code": "DUPLICATE_SKILL_VERSION",
        "message": "Skill version already exists: python.lint@1.2.3",
        "details": {"slug": "python.lint", "version": "1.2.3"},
    }
}

SKILL_ALREADY_EXISTS_ERROR_EXAMPLE = {
    "error": {
        "code": "SKILL_ALREADY_EXISTS",
        "message": "Skill already exists: python.lint",
        "details": {"slug": "python.lint"},
    }
}

SKILL_NOT_FOUND_ERROR_EXAMPLE = {
    "error": {
        "code": "SKILL_NOT_FOUND",
        "message": "Skill not found: python.lint",
        "details": {"slug": "python.lint"},
    }
}

SKILL_VERSION_NOT_FOUND_ERROR_EXAMPLE = {
    "error": {
        "code": "SKILL_VERSION_NOT_FOUND",
        "message": "Skill version not found: python.lint@9.9.9",
        "details": {"slug": "python.lint", "version": "9.9.9"},
    }
}

CONTENT_STORAGE_FAILURE_ERROR_EXAMPLE = {
    "error": {
        "code": "CONTENT_STORAGE_FAILURE",
        "message": "Failed to persist immutable skill version.",
    }
}

SKILL_VERSION_STATUS_RESPONSE_EXAMPLE = {
    "slug": "python.lint",
    "version": "1.2.3",
    "status": "deprecated",
    "trust_tier": "internal",
    "lifecycle_changed_at": "2026-03-11T09:15:00Z",
    "is_current_default": True,
}
