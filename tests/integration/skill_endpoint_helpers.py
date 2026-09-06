"""Shared helpers for registry endpoint integration tests."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.skills.bundle_archive import build_skill_bundle
from tests.conftest import DEFAULT_BEARER_TOKENS


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {DEFAULT_BEARER_TOKENS.get(token, token)}"}


def _token_record(
    *,
    token_id: str,
    secret: str,
    scopes: list[str],
    namespace_grants: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "token_id": token_id,
        "secret_digest": hashlib.sha256(secret.encode("utf-8")).hexdigest(),
        "scopes": scopes,
        "active": True,
        "namespace_grants": namespace_grants,
    }


def _request(
    version: str,
    *,
    intent: str = "create_skill",
    raw_markdown: str = "# Python Lint\n\nLint Python files.\n",
    name: str = "Python Lint",
    description: str = "Linting skill",
    tags: list[str] | None = None,
    trust_tier: str = "untrusted",
    provenance: dict[str, str] | None = None,
    depends_on: list[dict[str, object]] | None = None,
    extends: list[dict[str, object]] | None = None,
    conflicts_with: list[dict[str, object]] | None = None,
    overlaps_with: list[dict[str, object]] | None = None,
    overall_score: float | None = None,
) -> dict[str, object]:
    return {
        "intent": intent,
        "version": version,
        "bundle_raw_markdown": raw_markdown,
        "metadata": {
            "name": name,
            "description": description,
            "tags": tags or ["python", "lint"],
            "token_estimate": 128,
            "maturity_score": 0.9,
            "security_score": 0.95,
            "overall_score": overall_score,
        },
        "governance": {
            "trust_tier": trust_tier,
            "provenance": provenance,
        },
        "relationships": {
            "depends_on": depends_on or [],
            "extends": extends or [],
            "conflicts_with": conflicts_with or [],
            "overlaps_with": overlaps_with or [],
        },
    }


def _test_skill_request(
    version: str,
    *,
    name: str,
    description: str,
    trust_tier: str,
    provenance: dict[str, str] | None = None,
) -> dict[str, object]:
    return _request(
        version,
        intent="create_skill",
        raw_markdown=f"# {name}\n\nTest-only fixture entry.\n",
        name=name,
        description=description,
        tags=["python", "test", "fixture", "integration"],
        trust_tier=trust_tier,
        provenance=provenance,
    )


def _publish(
    client: TestClient,
    slug: str,
    payload: dict[str, object],
    *,
    token: str = "publisher-token",
) -> dict[str, object]:
    metadata = dict(payload)
    raw_markdown = str(metadata.pop("bundle_raw_markdown"))
    response = client.post(
        f"/skills/{slug}",
        files={
            "metadata": (None, json.dumps(metadata), "application/json"),
            "bundle": ("skill.tar.zst", _bundle(raw_markdown), "application/zstd"),
        },
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _publish_response(
    client: TestClient,
    slug: str,
    payload: dict[str, object],
    *,
    token: str | None = "publisher-token",
) -> Any:
    metadata = dict(payload)
    raw_markdown = str(metadata.pop("bundle_raw_markdown"))
    headers = {} if token is None else _headers(token)
    return client.post(
        f"/skills/{slug}",
        files={
            "metadata": (None, json.dumps(metadata), "application/json"),
            "bundle": ("skill.tar.zst", _bundle(raw_markdown), "application/zstd"),
        },
        headers=headers,
    )


def _update_status(
    client: TestClient,
    *,
    slug: str,
    version: str,
    status: str,
    token: str = "admin-token",
    note: str | None = None,
) -> dict[str, object]:
    response = client.patch(
        f"/skills/{slug}/{version}/status",
        json={"status": status, "note": note},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _query_storage_counts(database_url: str, *, slug: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) AS version_count,
                            COUNT(DISTINCT skill_versions.content_fk) AS distinct_content_fk_count
                        FROM skill_versions
                        JOIN skills ON skills.id = skill_versions.skill_fk
                        WHERE skills.slug = :slug
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one()
            )
            content_count = connection.execute(
                text("SELECT COUNT(*) FROM skill_contents")
            ).scalar_one()
            return {
                "version_count": int(row["version_count"]),
                "distinct_content_fk_count": int(row["distinct_content_fk_count"]),
                "content_count": int(content_count),
            }
    finally:
        engine.dispose()


def _query_install_counts(database_url: str, *, slug: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT skills.install_count AS skill_install_count
                        FROM skills
                        WHERE skills.slug = :slug
                        """
                    ),
                    {"slug": slug},
                )
                .mappings()
                .one()
            )
            return {
                "skill_install_count": int(row["skill_install_count"]),
            }
    finally:
        engine.dispose()


def _query_embedding_statuses(database_url: str, *, slug: str) -> list[str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT skill_search_embeddings.index_status
                        FROM skill_search_embeddings
                        JOIN skill_versions
                            ON skill_versions.id = skill_search_embeddings.skill_version_fk
                        JOIN skills
                            ON skills.id = skill_versions.skill_fk
                        WHERE skills.slug = :slug
                        ORDER BY skill_versions.id
                        """
                    ),
                    {"slug": slug},
                )
                .scalars()
                .all()
            )
            return [str(item) for item in rows]
    finally:
        engine.dispose()


def _query_audit_events(database_url: str) -> list[dict[str, Any]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return [
                {
                    "event_type": str(row["event_type"]),
                    "payload": row["payload"],
                }
                for row in connection.execute(
                    text("SELECT event_type, payload FROM audit_events ORDER BY id")
                ).mappings()
            ]
    finally:
        engine.dispose()


def _bundle(markdown: str) -> bytes:
    return build_skill_bundle(markdown)
