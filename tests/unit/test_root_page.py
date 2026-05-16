"""Unit coverage for the registry landing page assets."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.interface.api.root import router


def test_root_page_links_svg_favicon() -> None:
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert '<link rel="icon" href="/favicon.svg" type="image/svg+xml">' in response.text


def test_favicon_serves_svg_logo() -> None:
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<svg" in response.text
