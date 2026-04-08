"""Regression coverage for the local Docker Compose stack wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_server_depends_on_successful_migration_before_starting() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    server_section = compose.split("  server:\n", maxsplit=1)[1].split(
        "\n  migrate:\n",
        maxsplit=1,
    )[0]

    assert "server:" in compose
    assert "migrate:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "migrate:" in server_section
    assert "condition: service_completed_successfully" in server_section


def test_server_and_migrate_are_available_without_profiles() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    server_section = compose.split("  server:\n", maxsplit=1)[1].split(
        "\n  migrate:\n",
        maxsplit=1,
    )[0]
    migrate_section = compose.split("  migrate:\n", maxsplit=1)[1].split(
        "\n  demo-seed:\n",
        maxsplit=1,
    )[0]

    assert 'profiles: ["observability"]' not in server_section
    assert 'profiles: ["observability"]' not in migrate_section
