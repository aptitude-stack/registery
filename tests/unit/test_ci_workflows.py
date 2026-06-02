"""Regression coverage for CI workflow orchestration."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github/workflows"


def workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text()


@pytest.mark.unit
def test_ci_uses_four_explicit_branch_lifecycle_workflows() -> None:
    assert {path.name for path in WORKFLOWS_DIR.glob("*.yml")} == {
        "dev-pr-ci.yml",
        "dev-push-ci.yml",
        "master-pr-ci.yml",
        "master-push-ci.yml",
    }

    assert not (WORKFLOWS_DIR / "dev-merge-ci.yml").exists()
    assert not (WORKFLOWS_DIR / "main-ci.yml").exists()
    assert not (WORKFLOWS_DIR / "release-ci.yml").exists()


@pytest.mark.unit
def test_dev_pr_ci_keeps_pr_gate_without_docker_publish_or_production_secrets() -> None:
    document = workflow("dev-pr-ci.yml")

    assert "name: Dev PR CI" in document
    assert "pull_request:" in document
    assert "      - dev" in document
    assert "push:" not in document
    assert "name: Dev PR Gate" in document
    assert "run: make _ci-quality" in document
    assert "run: make _ci-test" in document
    assert "run: make _ci-image" not in document
    assert "make _ci-smoke" not in document
    assert "Docker Publish" not in document
    assert "docker/login-action@v3" not in document
    assert "docker/build-push-action@v6" not in document
    assert "MIGRATION_DATABASE_URL" not in document
    assert "RENDER_DEPLOY_HOOK_URL" not in document
    assert "make _ci-production-smoke" not in document
    assert "branches:\n      - master" not in document


@pytest.mark.unit
def test_dev_push_ci_builds_smokes_and_publishes_dev_images() -> None:
    document = workflow("dev-push-ci.yml")

    assert "name: Dev Push CI" in document
    assert "pull_request:" not in document
    assert "push:" in document
    assert "      - dev" in document
    assert "name: Docker Build and Smoke" in document
    assert "name: Docker Publish" in document
    assert "needs:\n      - docker-build-smoke" in document
    assert "run: make _ci-quality" in document
    assert "run: make _ci-test" in document
    assert "run: make _ci-image" in document
    assert "run: APP_IMAGE=y0ncha/aptitude-registry:latest make _ci-smoke" in document
    assert "run: make _ci-down" in document
    assert "Log in to Docker Hub" in document
    assert "docker/login-action@v3" in document
    assert "docker/build-push-action@v6" in document
    assert "type=raw,value=dev" in document
    assert "type=sha,prefix=sha-" in document
    assert "type=raw,value=latest" not in document
    assert "MIGRATION_DATABASE_URL" not in document
    assert "RENDER_DEPLOY_HOOK_URL" not in document
    assert "make _ci-production-smoke" not in document
    assert "branches:\n      - master" not in document


@pytest.mark.unit
def test_master_pr_ci_keeps_production_branch_gate_without_deployment() -> None:
    document = workflow("master-pr-ci.yml")

    assert "name: Master PR CI" in document
    assert "pull_request:" in document
    assert "      - master" in document
    assert "push:" not in document
    assert "name: Master PR Gate" in document
    assert "run: make _ci-quality" in document
    assert "run: make _ci-test" in document
    assert "run: make _ci-image" not in document
    assert "make _ci-smoke" not in document
    assert "docker/login-action@v3" not in document
    assert "docker/build-push-action@v6" not in document
    assert "MIGRATION_DATABASE_URL" not in document
    assert "RENDER_DEPLOY_HOOK_URL" not in document
    assert "make _ci-production-smoke" not in document
    assert "branches:\n      - dev" not in document


@pytest.mark.unit
def test_master_push_ci_migrates_deploys_and_smokes_production_after_final_gate() -> None:
    document = workflow("master-push-ci.yml")

    assert "name: Master Push CI" in document
    assert "pull_request:" not in document
    assert "push:" in document
    assert "      - master" in document
    assert "deployments: write" in document
    assert "name: Final Local Gate" in document
    assert "name: Migrate Neon and Deploy Render" in document
    assert "needs:\n      - final-local-gate" in document
    assert "run: make _ci-quality" in document
    assert "run: make _ci-test" in document
    assert "docker/setup-buildx-action@v3" not in document
    assert "run: make _ci-image" not in document
    assert "make _ci-smoke" not in document
    assert "run: make _ci-down" not in document
    assert "DATABASE_URL: ${{ secrets.MIGRATION_DATABASE_URL }}" in document
    assert "MIGRATION_DATABASE_URL: ${{ secrets.MIGRATION_DATABASE_URL }}" in document
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in document
    assert 'SEMANTIC_DISCOVERY_MODE: "off"' not in document
    assert "RENDER_DEPLOY_HOOK_URL: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}" in document
    assert ': "${OPENAI_API_KEY:?OPENAI_API_KEY GitHub secret is required}"' in document
    assert "uv run python scripts/check_openai_embeddings.py" in document
    assert document.index("uv run python scripts/check_openai_embeddings.py") < document.index(
        "uv run alembic upgrade head"
    )
    assert document.index("uv run python scripts/check_openai_embeddings.py") < document.index(
        "Trigger Render deploy for this commit"
    )
    assert "uv run alembic upgrade head" in document
    assert "uv run python scripts/check_alembic_at_head.py" in document
    assert "Create GitHub production deployment" in document
    assert "repos/${GITHUB_REPOSITORY}/deployments" in document
    assert "-f environment=production" in document
    assert "-F production_environment=true" in document
    assert "Mark GitHub deployment in progress" in document
    assert "ref=${REF}" in document
    assert "PRODUCTION_BASE_URL: ${{ vars.PRODUCTION_BASE_URL }}" in document
    assert (
        'run: PRODUCTION_BASE_URL="${PRODUCTION_BASE_URL:-https://api.aptitude-registry.dev}" '
        "make _ci-production-smoke" in document
    )
    assert "Mark GitHub deployment successful" in document
    assert "-f state=success" in document
    assert "Mark GitHub deployment failed" in document
    assert "-f state=failure" in document
    assert "Docker Publish" not in document
    assert "docker/login-action@v3" not in document
    assert "docker/build-push-action@v6" not in document
    assert "branches:\n      - dev" not in document


@pytest.mark.unit
def test_vercel_serverless_deployment_artifacts_are_absent() -> None:
    assert not (REPO_ROOT / "api/index.py").exists()
    assert not (REPO_ROOT / "server.py").exists()
    assert not (REPO_ROOT / "vercel.json").exists()
    assert not (REPO_ROOT / ".vercelignore").exists()


@pytest.mark.unit
def test_render_blueprint_declares_semantic_indexing_or_explicit_fallback() -> None:
    blueprint = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "aptitude-registry-api" in blueprint
    assert (
        "aptitude-registry-semantic-indexing" in blueprint
        or "semantic-indexing-managed-outside-blueprint" in blueprint
    )
