"""Regression coverage for CI workflow orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_dev_pr_ci_keeps_pr_gate_without_push_or_publish_jobs() -> None:
    document = (REPO_ROOT / ".github/workflows/dev-pr-ci.yml").read_text()

    assert "name: Dev PR CI" in document
    assert "pull_request:" in document
    assert "      - dev" in document
    assert "push:" not in document
    assert "services:" not in document
    assert "docker compose --ansi=never --progress=plain up -d db" not in document
    assert "name: Dev PR Gate" in document
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
    assert "Dev Merge Gate" not in document
    assert "Docker Publish" not in document
    assert "Log in to Docker Hub" not in document
    assert "docker/login-action@v3" not in document
    assert "docker/build-push-action@v6" not in document
    assert "branches:\n      - master" not in document


@pytest.mark.unit
def test_dev_merge_ci_keeps_post_merge_gate_and_publishes_dev_images() -> None:
    document = (REPO_ROOT / ".github/workflows/dev-merge-ci.yml").read_text()

    assert "name: Dev Merge CI" in document
    assert "pull_request:" not in document
    assert "push:" in document
    assert "      - dev" in document
    assert "services:" not in document
    assert "docker compose --ansi=never --progress=plain up -d db" not in document
    assert "name: Dev Merge Gate" in document
    assert "name: Docker Publish" in document
    assert "needs:\n      - dev-merge-gate" in document
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
    assert "Log in to Docker Hub" in document
    assert "docker/login-action@v3" in document
    assert "docker/build-push-action@v6" in document
    assert "type=raw,value=dev" in document
    assert "type=sha,prefix=sha-" in document
    assert "type=raw,value=latest" not in document
    assert "branches:\n      - master" not in document


@pytest.mark.unit
def test_main_ci_keeps_master_gate_without_owning_vercel_deployments() -> None:
    document = (REPO_ROOT / ".github/workflows/main-ci.yml").read_text()

    assert "pull_request:" in document
    assert "push:" in document
    assert "branches:\n      - master" in document
    assert "name: Master Main Gate" in document
    assert "run: uv sync --extra dev --frozen" in document
    assert "run: make _ci-quality" in document
    assert "run: make _ci-test" in document
    assert "run: make _ci-observability" in document
    assert "run: make _ci-image" in document
    assert (
        "TEST_DATABASE_URL: "
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test" in document
    )
    assert "run: APP_IMAGE=y0ncha/aptitude-registry:latest make _ci-smoke" in document
    assert "run: make _ci-down" in document
    assert "vercel pull" not in document
    assert "vercel build" not in document
    assert "vercel deploy" not in document
    assert "VERCEL_TOKEN" not in document
    assert "VERCEL_ORG_ID" not in document
    assert "VERCEL_PROJECT_ID" not in document
    assert "docker/build-push-action" not in document
    assert "docker/login-action" not in document


@pytest.mark.unit
def test_vercel_deployments_are_limited_to_production_track_branches() -> None:
    config = json.loads((REPO_ROOT / "vercel.json").read_text())

    assert config["regions"] == ["fra1"]
    assert (
        config["ignoreCommand"]
        == 'case "$VERCEL_GIT_COMMIT_REF" in master|release/*|hotfix/*) exit 1 ;; *) exit 0 ;; esac'
    )


@pytest.mark.unit
def test_release_ci_is_retired_to_avoid_duplicate_docker_publishing() -> None:
    assert not (REPO_ROOT / ".github/workflows/release-ci.yml").exists()
