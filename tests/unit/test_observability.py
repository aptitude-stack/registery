"""Unit tests for request-scoped observability helpers and metrics."""

from __future__ import annotations

import importlib

import pytest

from app.observability.context import (
    clear_request_context,
    get_request_context,
    set_request_context,
)


@pytest.mark.unit
def test_request_context_round_trips_and_clears() -> None:
    clear_request_context()
    set_request_context(
        request_id="req-456",
        http_method="POST",
        http_route="/discovery",
        status_code=401,
        duration_ms=8.0,
        client_ip="127.0.0.1",
        user_agent="pytest",
        surface="discovery",
        outcome="client_error",
        error_code="AUTHENTICATION_REQUIRED",
        exception_type="ApiError",
    )

    context = get_request_context()
    assert context.request_id == "req-456"
    assert context.http_method == "POST"
    assert context.http_route == "/discovery"
    assert context.status_code == 401
    assert context.duration_ms == 8.0
    assert context.client_ip == "127.0.0.1"
    assert context.user_agent == "pytest"
    assert context.surface == "discovery"
    assert context.outcome == "client_error"
    assert context.error_code == "AUTHENTICATION_REQUIRED"
    assert context.exception_type == "ApiError"

    clear_request_context()
    cleared = get_request_context()
    assert cleared.request_id is None
    assert cleared.http_method is None
    assert cleared.http_route is None
    assert cleared.status_code is None
    assert cleared.duration_ms is None
    assert cleared.client_ip is None
    assert cleared.user_agent is None
    assert cleared.surface is None
    assert cleared.outcome is None
    assert cleared.error_code is None
    assert cleared.exception_type is None


@pytest.mark.unit
def test_metrics_module_exposes_expected_aptitude_instruments() -> None:
    """A request through observe_http_request should emit instruments with the
    expected names. We install a temporary in-memory MeterProvider, reload the
    metrics module so its proxy instruments rebind to it, then verify the
    emitted metric names."""
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    from tests.unit._otel_helpers import reset_otel_globals

    reset_otel_globals()
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    otel_metrics.set_meter_provider(provider)
    try:
        metrics_module = importlib.import_module("app.observability.metrics")
        importlib.reload(metrics_module)
        metrics_module.observe_http_request(
            method="POST",
            route="/skills/{slug}",
            status_code=201,
            duration_seconds=0.123,
        )
        metrics_module.set_database_readiness(is_ready=True)

        data = reader.get_metrics_data()
        emitted: set[str] = set()
        if data is not None:
            for resource_metrics in data.resource_metrics:
                for scope_metrics in resource_metrics.scope_metrics:
                    for metric in scope_metrics.metrics:
                        emitted.add(metric.name)

        assert "aptitude_http_requests_total" in emitted
        assert "aptitude_http_request_duration_seconds" in emitted
        assert "aptitude_registry_operation_total" in emitted
        assert "aptitude_registry_operation_duration_seconds" in emitted
        assert "aptitude_readiness_status" in emitted
    finally:
        provider.shutdown()
        reset_otel_globals()
        importlib.reload(importlib.import_module("app.observability.metrics"))
