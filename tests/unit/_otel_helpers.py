"""OpenTelemetry private-state helpers used by unit tests.

The OTel SDK's `set_*_provider` functions are "set-once": after a global
TracerProvider / MeterProvider / LoggerProvider has been installed, subsequent
attempts to replace it log a warning and silently no-op. That breaks test
isolation when more than one test wants to install its own SDK. This helper
reaches into SDK private globals so each test can start from a clean slate.
"""

from __future__ import annotations


def reset_otel_globals() -> None:
    """Reset OTel SDK global providers so a new one can be installed."""
    import opentelemetry._logs._internal as logs_internal
    import opentelemetry.metrics._internal as metrics_internal
    import opentelemetry.trace as trace_module

    trace_module._TRACER_PROVIDER_SET_ONCE._done = False
    trace_module._TRACER_PROVIDER = None

    metrics_internal._METER_PROVIDER_SET_ONCE._done = False
    metrics_internal._METER_PROVIDER = None
    proxy_meter_provider = getattr(metrics_internal, "_PROXY_METER_PROVIDER", None)
    if proxy_meter_provider is not None:
        proxy_meter_provider._real_meter_provider = None  # type: ignore[attr-defined]

    logs_internal._LOGGER_PROVIDER_SET_ONCE._done = False
    logs_internal._LOGGER_PROVIDER = None
