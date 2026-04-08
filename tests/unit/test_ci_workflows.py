"""Regression coverage for CI workflow database orchestration."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DB_BOOT_PATTERN = re.compile(r"docker compose(?: [^\n]+)? up -d db")
DB_READY_PATTERN = re.compile(
    r"docker compose(?: [^\n]+)? exec -T db pg_isready -U postgres -d aptitude"
)


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
    boot_match = DB_BOOT_PATTERN.search(document)
    ready_match = DB_READY_PATTERN.search(document)

    assert "services:" not in document
    assert boot_match is not None
    assert ready_match is not None
    assert boot_match.start() < document.index("run: make migrate-up")
    assert boot_match.start() < document.index("run: make test-integration")
    assert boot_match.start() < ready_match.start()
