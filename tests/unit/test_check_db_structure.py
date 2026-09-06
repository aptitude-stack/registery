"""Unit contracts for the populated database cleanup preflight."""

from __future__ import annotations

import pytest

from scripts.check_db_structure import (
    compare_reports,
    fingerprint_rows,
    migration_database_url,
)


@pytest.mark.unit
def test_migration_database_url_requires_explicit_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="MIGRATION_DATABASE_URL"):
        migration_database_url()


@pytest.mark.unit
def test_migration_database_url_rejects_neon_pooler_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL",
        "postgresql+psycopg://user:password@ep-example-pooler.eu-central-1.aws.neon.tech/db",
    )

    with pytest.raises(ValueError, match="direct"):
        migration_database_url()


@pytest.mark.unit
def test_fingerprint_rows_hashes_binary_values_without_exposing_them() -> None:
    report = fingerprint_rows(
        {
            "skill_contents": [
                {"id": 4, "payload": b"private artifact bytes", "checksum_digest": "a" * 64}
            ]
        }
    )

    assert report["tables"]["skill_contents"]["rows"] == 1
    assert "private artifact bytes" not in str(report)
    assert "payload" not in str(report["tables"]["skill_contents"])
    assert len(report["digest"]) == 64


@pytest.mark.unit
def test_compare_reports_detects_canonical_drift_and_keeps_advisories_nonblocking() -> None:
    before = {
        "phase": "before",
        "canonical_fingerprint": {"digest": "a" * 64},
        "blocking_violations": [],
        "advisories": [{"code": "historical_star_count_discrepancy"}],
    }
    after = {
        "phase": "after",
        "canonical_fingerprint": {"digest": "b" * 64},
        "blocking_violations": [],
        "advisories": [],
    }

    comparison = compare_reports(before, after)

    assert comparison["ok"] is False
    assert comparison["blocking_violations"] == [{"code": "canonical_fingerprint_changed"}]
    assert comparison["advisories"] == []
