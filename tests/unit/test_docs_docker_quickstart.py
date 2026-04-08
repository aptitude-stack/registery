"""Regression coverage for Docker quick-start documentation."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_readme_quick_start_documents_docker_profiles_and_demo_seed_flow() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Quick Start" in readme
    assert "Docker" in readme
    assert "### Clean Run" in readme
    assert "### Demo Run" in readme
    assert "### Observability Run" in readme
    assert "docker compose up -d server" in readme
    assert "docker compose --profile observability up -d server observability" in readme
    assert "docker compose --profile demo run --rm demo-seed" in readme
    assert "docker compose down -v" in readme
    assert "Database only:" not in readme


def test_development_setup_documents_demo_seed_flow() -> None:
    guide = (REPO_ROOT / "docs/contributors/development-setup.md").read_text(encoding="utf-8")

    assert "demo profile" in guide.lower()
    assert "docker compose up -d server" in guide
    assert "docker compose --profile demo run --rm demo-seed" in guide
    assert "docker compose --profile observability up -d server observability" in guide
