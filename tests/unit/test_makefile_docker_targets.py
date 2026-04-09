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
            "image-push",
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
def test_demo_make_targets_run_profiled_demo_seed_and_demo_stack() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "stack",
            "stack-demo",
            "stack-observability",
            "stack-observability-demo",
            "smoke-demo",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "docker compose --profile demo run --rm demo-seed" in result.stdout
    assert result.stdout.count("docker compose --profile demo run --rm demo-seed") >= 2
    assert "docker compose up -d server" in result.stdout
    assert "docker compose up -d db" in result.stdout
    assert "docker compose --profile observability up -d server observability" in result.stdout
    assert result.stdout.count("docker compose rm -f -s migrate") >= 2


@pytest.mark.unit
def test_integration_db_make_targets_manage_dedicated_test_database() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "db-test",
            "tests-integration-container",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "docker compose --profile test up -d test-db" in result.stdout
    assert (
        "docker compose --profile test exec -T test-db pg_isready -U postgres -d aptitude_test"
        in result.stdout
    )
    assert (
        "TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/aptitude_test"
        in result.stdout
    )
    assert "python -m pytest tests/integration" in result.stdout
    assert "docker compose --profile test rm -f -s -v test-db" in result.stdout
    assert "docker volume rm -f aptitude-test-postgres-data" in result.stdout


@pytest.mark.unit
def test_tests_runs_full_suite_with_managed_test_database() -> None:
    result = subprocess.run(
        [
            "make",
            "-n",
            "tests",
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
