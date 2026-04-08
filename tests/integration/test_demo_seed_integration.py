"""Integration coverage for the demo catalog seeding workflow."""

from __future__ import annotations

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from alembic import command
from app.bootstrap.seed_demo import run_demo_seed
from app.main import create_app


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def migrated_registry_database(clean_integration_database: str) -> str:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", clean_integration_database)
    command.upgrade(config, "head")
    return clean_integration_database


@pytest.mark.integration
def test_demo_seed_populates_registry_and_is_visible_via_existing_api(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    first = run_demo_seed()
    second = run_demo_seed()

    assert first.published_count == 10
    assert first.status_updated_count == 3
    assert second.published_count == 0
    assert second.skipped_existing_count == 10

    engine = create_engine(migrated_registry_database)
    try:
        with engine.connect() as connection:
            version_count = connection.execute(
                text("SELECT COUNT(*) FROM skill_versions")
            ).scalar_one()
    finally:
        engine.dispose()

    assert version_count == 10

    with TestClient(create_app()) as client:
        lint_versions = client.get("/skills/python.lint", headers=_headers("reader-token"))
        format_versions_reader = client.get(
            "/skills/python.format",
            headers=_headers("reader-token"),
        )
        format_versions_admin = client.get("/skills/python.format", headers=_headers("admin-token"))
        format_archived_reader = client.get(
            "/skills/python.format/1.0.0",
            headers=_headers("reader-token"),
        )
        format_archived_admin = client.get(
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
        security_metadata = client.get(
            "/skills/python.security.scan/1.0.0",
            headers=_headers("reader-token"),
        )

    assert lint_versions.status_code == 200
    assert [item["version"] for item in lint_versions.json()["versions"]] == ["2.0.0", "1.0.0"]
    assert lint_versions.json()["versions"][0]["is_current_default"] is True
    assert lint_versions.json()["versions"][1]["lifecycle_status"] == "deprecated"

    assert format_versions_reader.status_code == 200
    assert [item["version"] for item in format_versions_reader.json()["versions"]] == ["2.0.0"]
    assert format_versions_admin.status_code == 200
    assert [item["version"] for item in format_versions_admin.json()["versions"]] == [
        "2.0.0",
        "1.0.0",
    ]
    assert format_versions_admin.json()["versions"][1]["lifecycle_status"] == "archived"

    assert format_archived_reader.status_code == 403
    assert format_archived_reader.json()["error"]["code"] == "POLICY_EXACT_READ_FORBIDDEN"
    assert format_archived_admin.status_code == 200
    assert format_archived_admin.json()["version"] == "1.0.0"

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

    assert security_metadata.status_code == 200
    assert security_metadata.json()["trust_tier"] == "verified"
    assert security_metadata.json()["provenance"]["repo_url"].startswith("https://github.com/")
    assert security_metadata.json()["provenance"]["publisher_identity"]
