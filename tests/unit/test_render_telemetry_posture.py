"""Regression coverage for Render telemetry defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_render_blueprint_keeps_otel_dormant_by_default() -> None:
    document = (REPO_ROOT / "render.yaml").read_text()

    assert "buildCommand: uv sync --frozen --no-dev\n" in document
    assert "--extra otel" not in document
    assert "      - key: OTEL_ENABLED\n        value: \"false\"\n" in document
    assert "      - key: OTEL_SDK_DISABLED\n        value: \"true\"\n" in document


@pytest.mark.unit
def test_render_blueprint_does_not_request_grafana_exporter_secrets() -> None:
    document = (REPO_ROOT / "render.yaml").read_text()

    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in document
    assert "OTEL_EXPORTER_OTLP_HEADERS" not in document
    assert "OTEL_RESOURCE_ATTRIBUTES" not in document
