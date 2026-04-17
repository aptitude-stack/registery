"""Regression coverage for Docker and observability Make targets."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_docker_build_push_bootstraps_and_uses_named_builder() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "build",
            "DOCKER_BUILDER=ci-builder",
            "DOCKER_IMAGE=example/image",
            "DOCKER_TAG=test",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        "docker buildx inspect ci-builder >/dev/null 2>&1 || "
        "docker buildx create --name ci-builder --driver docker-container >/dev/null"
        in result.stdout
    )
    assert "docker buildx inspect --bootstrap ci-builder >/dev/null" in result.stdout
    assert (
        "docker buildx build --builder ci-builder --platform linux/amd64,linux/arm64 "
        "--push -t example/image:test ." in result.stdout
    )


@pytest.mark.unit
def test_run_dev_bootstraps_demo_seed_and_observability() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "run-dev",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "APP_ENV=dev docker compose up -d db" in result.stdout
    assert "APP_ENV=dev docker compose build server migrate demo-seed" in result.stdout
    assert "docker compose --profile demo run --rm demo-seed" in result.stdout
    assert (
        "APP_ENV=dev docker compose --profile observability up -d server observability"
        in result.stdout
    )
    assert "APP_ENV=dev docker compose rm -f -s migrate" in result.stdout


@pytest.mark.unit
def test_run_prod_omits_demo_seed_but_keeps_observability() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "run-prod",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "APP_ENV=prod docker compose up -d db" in result.stdout
    assert "APP_ENV=prod docker compose build server migrate" in result.stdout
    assert "APP_ENV=prod docker compose build server migrate demo-seed" not in result.stdout
    assert "docker compose --profile demo run --rm demo-seed" not in result.stdout
    assert (
        "APP_ENV=prod docker compose --profile observability up -d server observability"
        in result.stdout
    )


@pytest.mark.unit
def test_test_runs_full_suite_with_managed_test_database() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "test",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        "TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test"
        in result.stdout
    )
    assert "python -m pytest" in result.stdout
    assert 'python -m pytest -m "not integration"' not in result.stdout
    assert "python -m pytest tests/integration" not in result.stdout
    assert "docker compose --profile test up -d test-db" in result.stdout
    assert (
        "docker compose --profile test exec -T test-db pg_isready -U postgres -d aptitude_test"
        in result.stdout
    )
    assert "docker compose --profile test rm -f -s -v test-db" in result.stdout
    assert "docker volume rm -f aptitude-test-postgres-data" in result.stdout
