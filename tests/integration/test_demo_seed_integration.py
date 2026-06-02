"""Integration coverage for the demo catalog seeding workflow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.bootstrap.seed_demo import run_demo_seed
from app.main import create_app
from tests.conftest import DEFAULT_BEARER_TOKENS


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {DEFAULT_BEARER_TOKENS.get(token, token)}"}


def _query_seeded_catalog_state(database_url: str) -> dict[str, object]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                    SELECT
                        COUNT(*) AS version_count,
                        COUNT(*) FILTER (
                            WHERE skill_versions.lifecycle_status = 'archived'
                        ) AS archived_count,
                        COUNT(*) FILTER (
                            WHERE skill_versions.lifecycle_status = 'deprecated'
                        ) AS deprecated_count,
                        COUNT(*) FILTER (
                            WHERE skills.slug = 'python.format'
                            AND skill_versions.version = '1.0.0'
                            AND skill_versions.lifecycle_status = 'archived'
                        ) AS archived_format_count,
                        COUNT(*) FILTER (
                            WHERE skills.slug = 'python.lint'
                            AND skill_versions.version = '1.0.0'
                            AND skill_versions.lifecycle_status = 'deprecated'
                        ) AS deprecated_lint_count
                    FROM skill_versions
                    JOIN skills
                        ON skills.id = skill_versions.skill_fk
                    """
                    )
                )
                .mappings()
                .one()
            )
            return {
                "version_count": int(row["version_count"]),
                "archived_count": int(row["archived_count"]),
                "deprecated_count": int(row["deprecated_count"]),
                "archived_format_count": int(row["archived_format_count"]),
                "deprecated_lint_count": int(row["deprecated_lint_count"]),
            }
    finally:
        engine.dispose()


@pytest.mark.integration
def test_demo_seed_populates_registry_idempotently_and_exposes_seeded_behaviors(
    monkeypatch: pytest.MonkeyPatch,
    migrated_integration_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_integration_database)

    run_demo_seed()
    first_state = _query_seeded_catalog_state(migrated_integration_database)
    run_demo_seed()
    second_state = _query_seeded_catalog_state(migrated_integration_database)

    assert first_state == second_state
    assert second_state == {
        "version_count": 11,
        "archived_count": 1,
        "deprecated_count": 2,
        "archived_format_count": 1,
        "deprecated_lint_count": 1,
    }

    with TestClient(create_app()) as client:
        archived_reader = client.get(
            "/skills/python.format/1.0.0",
            headers=_headers("reader-token"),
        )
        archived_admin = client.get(
            "/skills/python.format/1.0.0",
            headers=_headers("admin-token"),
        )
        resolution = client.get(
            "/resolution/python.test/1.0.0",
            headers=_headers("reader-token"),
        )
        discovery = client.post(
            "/discovery",
            json={
                "name": "Python Code Quality Bundle",
                "description": "lint format test bundle",
                "tags": ["python", "quality", "bundle"],
            },
            headers=_headers("reader-token"),
        )
        docs_discovery = client.post(
            "/discovery",
            json={"name": "docs"},
            headers=_headers("reader-token"),
        )

    assert archived_reader.status_code == 403
    assert archived_reader.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert archived_admin.status_code == 200
    assert archived_admin.json()["version"] == "1.0.0"

    assert resolution.status_code == 200
    assert resolution.json()["depends_on"] == [
        {
            "slug": "python.base",
            "version": "1.1.0",
            "version_constraint": None,
            "optional": None,
            "markers": [],
        },
        {
            "slug": "python.lint",
            "version": None,
            "version_constraint": ">=2.0.0,<3.0.0",
            "optional": True,
            "markers": ["ci", "linux"],
        },
    ]

    assert discovery.status_code == 200
    assert "python.bundle.code-quality" in discovery.json()["candidates"]
    assert docs_discovery.status_code == 200
    assert "documentation-writing" in docs_discovery.json()["candidates"]
