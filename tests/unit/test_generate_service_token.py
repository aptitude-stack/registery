"""Unit tests for the production service-token generator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_generate_service_token_outputs_full_production_token_set() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate_service_token.py",
            "--secret",
            "fixed-secret",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "READ_TOKEN=reader-prod.fixed-secret" in result.stdout
    assert "TELEMETRY_TOKEN=telemetry_prod.fixed-secret" in result.stdout
    assert "PUBLISH_TOKEN=publisher-prod.fixed-secret" in result.stdout
    assert "ADMIN_TOKEN=admin-prod.fixed-secret" in result.stdout

    settings_line = next(
        line for line in result.stdout.splitlines() if line.startswith("AUTH_SERVICE_TOKENS_JSON=")
    )
    records = json.loads(settings_line.removeprefix("AUTH_SERVICE_TOKENS_JSON="))

    assert [record["token_id"] for record in records] == [
        "reader-prod",
        "telemetry_prod",
        "publisher-prod",
        "admin-prod",
    ]
    assert [record["scopes"] for record in records] == [
        ["read"],
        ["telemetry"],
        ["read", "publish"],
        ["read", "publish", "review", "admin"],
    ]
    assert records[1]["namespace_grants"] == []
    assert all(
        "telemetry" not in grant["roles"]
        for record in records
        for grant in record["namespace_grants"]
    )
