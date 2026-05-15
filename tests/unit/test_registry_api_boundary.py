"""Unit tests for the public registry API route surface."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import create_app


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

    assert ("/skills/{slug}", "POST") in routes
    assert ("/skills/{slug}", "GET") in routes
    assert ("/catalog/top-skills", "GET") in routes
    assert ("/catalog/search", "POST") in routes
    assert ("/discovery", "POST") in routes
    assert ("/resolution/{slug}/{version}", "GET") in routes
    assert ("/skills/{slug}/{version}", "GET") in routes
    assert ("/skills/{slug}/{version}/content", "GET") in routes
    assert ("/skills/{slug}/{version}/status", "PATCH") in routes
    assert ("/admin/organizations", "POST") in routes
    assert ("/admin/namespaces", "POST") in routes
    assert ("/admin/policy-packs/{slug}", "PUT") in routes
    assert ("/admin/skills/{slug}/ownership", "PATCH") in routes
    assert ("/admin/skills/{slug}/{version}/governance", "PATCH") in routes
    assert ("/admin/skills/{slug}/{version}/trust-evidence", "POST") in routes


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

    assert "/discovery" in paths
    assert "/catalog/top-skills" in paths
    assert "/catalog/search" in paths
    assert "/resolution/{slug}/{version}" in paths
    assert "/skills/{slug}" in paths
    assert "/skills/{slug}/{version}" in paths
    assert "/skills/{slug}/{version}/content" in paths
    assert "/admin/organizations" in paths
    assert "/admin/namespaces" in paths
    assert "/admin/policy-packs/{slug}" in paths
    assert "/admin/skills/{slug}/ownership" in paths
    assert "/admin/skills/{slug}/{version}/governance" in paths
    assert "/admin/skills/{slug}/{version}/trust-evidence" in paths
    assert "post" in paths["/skills/{slug}"]
    assert "get" in paths["/skills/{slug}"]
    assert "get" in paths["/catalog/top-skills"]
    assert "post" in paths["/catalog/search"]
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
def test_openapi_schema_excludes_admin_and_html_routes() -> None:
    """Admin/operational endpoints stay reachable but are filtered from the public schema."""
    schema = create_app().openapi()
    paths = schema["paths"]

    assert "/" not in paths
    assert "/metrics" not in paths
    assert "patch" not in paths.get("/skills/{slug}/{version}/status", {})
    assert "/skills/{slug}/{version}/status" not in paths


@pytest.mark.unit
@pytest.mark.parametrize("app_env", ["dev", "prod"])
def test_docs_and_openapi_are_public_in_all_envs(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    monkeypatch.setenv("APP_ENV", app_env)

    with TestClient(create_app()) as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert redoc.status_code == 200
    assert openapi.status_code == 200


@pytest.mark.unit
def test_prod_rejects_untrusted_host_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")

    with TestClient(create_app()) as client:
        response = client.get("/healthz", headers={"host": "evil.example"})

    assert response.status_code == 400


@pytest.mark.unit
def test_metrics_route_no_longer_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    """The /metrics Prometheus endpoint was removed when telemetry moved to OTLP push."""
    monkeypatch.setenv("APP_ENV", "prod")
    routes = _routes()

    assert ("/metrics", "GET") not in routes
