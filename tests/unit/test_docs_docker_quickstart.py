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
    assert "make stack" in readme
    assert "make stack-demo" in readme
    assert "make stack-observability" in readme
    assert "make tests-integration-container" in readme
    assert "127.0.0.1:5433/aptitude_test" in readme
    assert "make stack-down" in readme
    assert "Database only:" not in readme


def test_development_setup_documents_demo_seed_flow() -> None:
    guide = (REPO_ROOT / "docs/contributors/development-setup.md").read_text(encoding="utf-8")

    assert "demo profile" in guide.lower()
    assert "make stack" in guide
    assert "make stack-demo" in guide
    assert "make stack-observability" in guide
    assert "make stack-observability-demo" in guide
    assert "make db-test" in guide
    assert "make tests-integration-container" in guide
    assert "127.0.0.1:5433" in guide
