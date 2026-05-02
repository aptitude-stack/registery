"""Regression coverage for Docker quick-start documentation."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_readme_quick_start_documents_docker_profiles_and_demo_seed_flow() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Quick Start" in readme
    assert "Docker" in readme
    assert "make run-dev" in readme
    assert "make run-prod" in readme
    assert "make test" in readme
    assert "127.0.0.1:5433/aptitude_test" in readme
    assert "docker compose down -v" in readme
    assert "Database only:" not in readme


def test_development_setup_documents_demo_seed_flow() -> None:
    guide = (REPO_ROOT / "docs/contributors/development-setup.md").read_text(encoding="utf-8")

    assert "demo profile" in guide.lower()
    assert "make run-dev" in guide
    assert "make run-prod" in guide
    assert "make test" in guide
    assert "make quality" in guide
    assert "127.0.0.1:5433" in guide
