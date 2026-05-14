"""Service metrics emitted via the OpenTelemetry Meter API.

When OTel is active, instruments record into the global MeterProvider configured
in `app.observability.telemetry`, which forwards them to Grafana Cloud over
OTLP/HTTP. When OTel is inactive (default for tests and bare local runs),
`get_meter` returns a no-op proxy and the recorded measurements are dropped on
the floor.

Metric names, attribute keys, and bucket boundaries are kept identical to the
previous prometheus-client implementation so downstream dashboards continue to
work after the global MeterProvider is wired up.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from opentelemetry import metrics as otel_metrics
from opentelemetry.metrics import CallbackOptions, Observation

if TYPE_CHECKING:
    pass

HTTP_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
OPERATION_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

_meter = otel_metrics.get_meter("aptitude.registry")

HTTP_REQUESTS_TOTAL = _meter.create_counter(
    name="aptitude_http_requests_total",
    description="Total HTTP requests handled by the service.",
)
HTTP_REQUEST_DURATION_SECONDS = _meter.create_histogram(
    name="aptitude_http_request_duration_seconds",
    unit="s",
    description="HTTP request duration in seconds.",
    explicit_bucket_boundaries_advisory=list(HTTP_DURATION_BUCKETS),
)
REGISTRY_OPERATION_TOTAL = _meter.create_counter(
    name="aptitude_registry_operation_total",
    description="Total registry operations by surface and outcome.",
)
REGISTRY_OPERATION_DURATION_SECONDS = _meter.create_histogram(
    name="aptitude_registry_operation_duration_seconds",
    unit="s",
    description="Registry operation duration in seconds by surface.",
    explicit_bucket_boundaries_advisory=list(OPERATION_DURATION_BUCKETS),
)
SEMANTIC_DISCOVERY_FAILURES = _meter.create_counter(
    name="aptitude_semantic_discovery_failures_total",
    description="Semantic discovery fallback events by mode, stage, and exception type.",
)

_READINESS_STATE: dict[str, int] = {"database": 0}


def _readiness_callback(options: CallbackOptions) -> Iterable[Observation]:
    return [
        Observation(value=value, attributes={"dependency": dependency})
        for dependency, value in _READINESS_STATE.items()
    ]


READINESS_STATUS = _meter.create_observable_gauge(
    name="aptitude_readiness_status",
    callbacks=[_readiness_callback],
    description="Readiness state for critical dependencies.",
)


_ROUTE_TO_SURFACE: dict[tuple[str, str], str] = {
    ("POST", "/skills/{slug}"): "publish",
    ("POST", "/discovery"): "discovery",
    ("GET", "/skills/{slug}"): "list",
    ("GET", "/resolution/{slug}/{version}"): "resolution",
    ("GET", "/skills/{slug}/{version}"): "metadata",
    ("GET", "/skills/{slug}/{version}/content"): "content",
    ("PATCH", "/skills/{slug}/{version}/status"): "lifecycle",
}
_SYSTEM_ROUTES = frozenset({"/healthz", "/readyz"})


def observe_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record bounded HTTP and domain operation metrics."""
    normalized_method = method.upper()
    HTTP_REQUESTS_TOTAL.add(
        1,
        attributes={
            "method": normalized_method,
            "route": route,
            "status_class": _status_class(status_code),
        },
    )
    HTTP_REQUEST_DURATION_SECONDS.record(
        duration_seconds,
        attributes={"method": normalized_method, "route": route},
    )

    surface = _ROUTE_TO_SURFACE.get((normalized_method, route))
    if surface is None:
        return

    REGISTRY_OPERATION_TOTAL.add(
        1,
        attributes={"surface": surface, "outcome": outcome_for_status_code(status_code)},
    )
    REGISTRY_OPERATION_DURATION_SECONDS.record(
        duration_seconds,
        attributes={"surface": surface},
    )


def set_database_readiness(*, is_ready: bool) -> None:
    """Track whether the primary database dependency is reachable."""
    _READINESS_STATE["database"] = 1 if is_ready else 0


def observe_semantic_discovery_failure(
    *,
    mode: str,
    stage: str,
    exception_type: str,
) -> None:
    """Record one semantic discovery failure that degraded to lexical fallback."""
    SEMANTIC_DISCOVERY_FAILURES.add(
        1,
        attributes={
            "mode": mode,
            "stage": stage,
            "exception_type": exception_type,
        },
    )


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def outcome_for_status_code(status_code: int) -> str:
    if status_code < 400:
        return "success"
    if status_code < 500:
        return "client_error"
    return "server_error"


def surface_for_request(*, method: str, route: str) -> str | None:
    normalized_method = method.upper()
    surface = _ROUTE_TO_SURFACE.get((normalized_method, route))
    if surface is not None:
        return surface
    if route in _SYSTEM_ROUTES:
        return "system"
    return None
