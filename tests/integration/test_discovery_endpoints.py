"""Integration tests for discovery endpoints."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import create_app
from app.persistence.db import get_session_factory
from tests.integration.skill_endpoint_helpers import (
    _headers,
    _publish,
    _request,
)


@pytest.mark.integration
def test_discovery_queries_search_documents_without_touching_skill_contents(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)
    slug = f"python.discovery.metadata-only.{uuid4().hex}"

    with TestClient(create_app()) as client:
        _publish(
            client,
            slug,
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# Metadata Only Discovery\n",
                name="Metadata Only Discovery",
                description="Search document should satisfy discovery",
            ),
        )

        engine = get_session_factory().kw["bind"]
        executed_selects: list[str] = []

        def _capture_selects(
            _conn: Any,
            _cursor: Any,
            statement: str,
            _parameters: Any,
            _context: Any,
            _executemany: bool,
        ) -> None:
            normalized_statement = " ".join(statement.split())
            if normalized_statement.upper().startswith(("SELECT", "WITH")):
                executed_selects.append(normalized_statement)

        event.listen(engine, "before_cursor_execute", _capture_selects)
        try:
            response = client.post(
                "/discovery",
                json={"name": "Metadata Only Discovery"},
                headers=_headers("reader-token"),
            )
        finally:
            event.remove(engine, "before_cursor_execute", _capture_selects)

    assert response.status_code == 200
    assert response.json()["candidates"] == [slug]
    assert any("skill_search_documents" in statement for statement in executed_selects)
    assert all("skill_contents" not in statement for statement in executed_selects)


@pytest.mark.integration
@pytest.mark.parametrize("query_word", ["docs", "documentation", "writing"])
def test_discovery_word_queries_return_expected_documentation_skill(
    monkeypatch: pytest.MonkeyPatch,
    migrated_registry_database: str,
    query_word: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_registry_database)

    with TestClient(create_app()) as client:
        _publish(
            client,
            "documentation-writing",
            _request(
                "1.0.0",
                intent="create_skill",
                raw_markdown="# Documentation Writing\n\nWrite docs, guides, and references.\n",
                name="Documentation Writing",
                description="Write documentation, docs, guides, and API references.",
                tags=["documentation", "docs", "writing"],
            ),
        )
        response = client.post(
            "/discovery",
            json={"name": query_word},
            headers=_headers("reader-token"),
        )

    assert response.status_code == 200
    assert "documentation-writing" in response.json()["candidates"]
