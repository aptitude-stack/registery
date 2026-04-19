"""Unit tests for the public registry API route surface."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import DEFAULT_BEARER_TOKENS


def _routes() -> set[tuple[str, str]]:
    app = create_app()
    return {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


@pytest.mark.unit
def test_public_route_surface_exposes_exact_get_fetch_routes() -> None:
    routes = _routes()

    assert ("/metrics", "GET") in routes
    assert ("/skills/{slug}", "POST") in routes
    assert ("/skills/{slug}", "GET") in routes
    assert ("/discovery", "POST") in routes
    assert ("/resolution/{slug}/{version}", "GET") in routes
    assert ("/skills/{slug}/{version}", "GET") in routes
    assert ("/skills/{slug}/{version}/content", "GET") in routes
    assert ("/skills/{slug}/{version}/status", "PATCH") in routes


@pytest.mark.unit
def test_public_route_surface_is_identical_across_runtime_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    dev_routes = _routes()

    monkeypatch.setenv("APP_ENV", "prod")
    prod_routes = _routes()

    assert dev_routes == prod_routes


@pytest.mark.unit
def test_public_route_surface_excludes_removed_route_families() -> None:
    routes = _routes()

    assert ("/skill-versions", "POST") not in routes
    assert ("/discovery/skills/search", "GET") not in routes
    assert ("/resolution/relationships:batch", "POST") not in routes
    assert ("/fetch/metadata:batch", "POST") not in routes
    assert ("/fetch/content:batch", "POST") not in routes
    assert ("/skills/{slug}/versions", "POST") not in routes
    assert ("/skills/{slug}/versions", "GET") not in routes
    assert ("/skills/{slug}/versions/{version}", "GET") not in routes
    assert ("/skills/{slug}/versions/{version}/content", "GET") not in routes
    assert ("/skills/{slug}/versions/{version}/status", "PATCH") not in routes


@pytest.mark.unit
def test_openapi_contract_matches_exact_get_fetch_routes() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    multipart_request = paths["/skills/{slug}"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]
    publish_request = multipart_request["schema"]
    publish_properties = publish_request["properties"]
    publish_encoding = multipart_request["encoding"]
    content_success = paths["/skills/{slug}/{version}/content"]["get"]["responses"]["200"][
        "content"
    ]

    assert "/metrics" in paths
    assert "/discovery" in paths
    assert "/resolution/{slug}/{version}" in paths
    assert "/skills/{slug}" in paths
    assert "/skills/{slug}/{version}" in paths
    assert "/skills/{slug}/{version}/content" in paths
    assert "get" in paths["/metrics"]
    assert "post" in paths["/skills/{slug}"]
    assert "get" in paths["/skills/{slug}"]
    assert "post" in paths["/discovery"]
    assert "get" in paths["/resolution/{slug}/{version}"]
    assert "get" in paths["/skills/{slug}/{version}"]
    assert "get" in paths["/skills/{slug}/{version}/content"]
    assert "/skill-versions" not in paths
    assert "/discovery/skills/search" not in paths
    assert "/resolution/relationships:batch" not in paths
    assert "/fetch/metadata:batch" not in paths
    assert "/fetch/content:batch" not in paths
    assert "/skills/{slug}/versions" not in paths
    assert "metadata" in publish_properties
    assert "bundle" in publish_properties
    assert "metadata" in publish_request["required"]
    assert "bundle" in publish_request["required"]
    assert "slug" not in publish_properties
    assert publish_encoding["bundle"]["contentType"] == "application/zstd"
    assert "application/zstd" in content_success


@pytest.mark.unit
def test_prod_disables_docs_and_openapi_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    with TestClient(create_app()) as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        openapi = client.get("/openapi.json")

    assert docs.status_code == 404
    assert redoc.status_code == 404
    assert openapi.status_code == 404


@pytest.mark.unit
def test_dev_keeps_docs_and_openapi_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")

    with TestClient(create_app()) as client:
        docs = client.get("/docs")
        openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert openapi.status_code == 200


@pytest.mark.unit
def test_prod_rejects_untrusted_host_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    with TestClient(create_app()) as client:
        response = client.get("/healthz", headers={"host": "evil.example"})

    assert response.status_code == 400


@pytest.mark.unit
def test_metrics_requires_admin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    with TestClient(create_app()) as client:
        missing = client.get("/metrics")
        reader = client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {DEFAULT_BEARER_TOKENS['reader-token']}"},
        )
        admin = client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {DEFAULT_BEARER_TOKENS['admin-token']}"},
        )

    assert missing.status_code == 401
    assert reader.status_code == 403
    assert admin.status_code == 200
