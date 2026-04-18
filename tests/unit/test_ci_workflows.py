"""Regression coverage for CI workflow database orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.parametrize(
    "workflow_path",
    [
        ".github/workflows/main-ci.yml",
        ".github/workflows/dev-ci.yml",
    ],
)
def test_ci_workflows_boot_runner_tests_from_compose_db(workflow_path: str) -> None:
    document = (REPO_ROOT / workflow_path).read_text()

    assert "services:" not in document
    assert "docker compose --ansi=never --progress=plain up -d db" not in document
    assert "run: make _ci-quality" in document
    assert "run: make _ci-test" in document
    assert "run: make _ci-observability" in document
    assert "run: make _ci-image" in document
    assert (
        "TEST_DATABASE_URL: "
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test" in document
    )
    assert "Run smoke gate" in document
    assert "run: APP_IMAGE=y0ncha/aptitude-registry:latest make _ci-smoke" in document
    assert "run: make _ci-down" in document
    assert "test-integration-docker" not in document
    assert "docker-smoke" not in document
    assert "observability-down" not in document


@pytest.mark.unit
def test_release_ci_remains_image_focused_and_avoids_test_db_bootstrap() -> None:
    document = (REPO_ROOT / ".github/workflows/release-ci.yml").read_text()

    assert "docker/build-push-action@v6" in document
    assert "make _ci-test" not in document
    assert "docker compose --profile test" not in document
    assert "TEST_DATABASE_URL" not in document
    assert '      - "Dockerfile"' in document
    assert '      - ".dockerignore"' in document
    assert '      - "app/**"' in document
    assert '      - "alembic/**"' in document
    assert '      - "alembic.ini"' in document
    assert '      - "pyproject.toml"' in document
    assert '      - "uv.lock"' in document
