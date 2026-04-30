"""Regression coverage for CI workflow orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_dev_ci_keeps_pr_gate_and_publishes_dev_images_after_merge() -> None:
    document = (REPO_ROOT / ".github/workflows/dev-ci.yml").read_text()

    assert "pull_request:" in document
    assert "      - dev" in document
    assert "push:" in document
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
    assert "Log in to Docker Hub" in document
    assert "docker/login-action@v3" in document
    assert "docker/build-push-action@v6" in document
    assert "type=raw,value=dev" in document
    assert "type=sha,prefix=sha-" in document
    assert "type=raw,value=latest" not in document
    assert "branches:\n      - master" not in document


@pytest.mark.unit
def test_main_ci_owns_vercel_preview_and_production_deployments() -> None:
    document = (REPO_ROOT / ".github/workflows/main-ci.yml").read_text()

    assert "pull_request:" in document
    assert "push:" in document
    assert "branches:\n      - master" in document
    assert "VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}" in document
    assert "VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}" in document
    assert "npm install --global vercel@latest" in document
    assert "vercel pull --yes --environment=preview --token=${{ secrets.VERCEL_TOKEN }}" in document
    assert "vercel build --token=${{ secrets.VERCEL_TOKEN }}" in document
    assert "vercel deploy --prebuilt --token=${{ secrets.VERCEL_TOKEN }}" in document
    assert (
        "vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}" in document
    )
    assert "vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}" in document
    assert "vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}" in document
    assert "make _ci-image" not in document
    assert "make _ci-smoke" not in document
    assert "docker/build-push-action" not in document
    assert "docker/login-action" not in document


@pytest.mark.unit
def test_release_ci_is_retired_to_avoid_duplicate_docker_publishing() -> None:
    assert not (REPO_ROOT / ".github/workflows/release-ci.yml").exists()
