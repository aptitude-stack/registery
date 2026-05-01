"""OpenTelemetry SDK bootstrap for Grafana Cloud.

Wires global TracerProvider, LoggerProvider, and MeterProvider against an
OTLP/HTTP backend. Endpoint, headers, sampler, and protocol are read from the
standard `OTEL_*` environment variables, so this module stays free of
backend-specific configuration.

When `Settings.otel_enabled` is False (the default) or the standard
`OTEL_SDK_DISABLED=true` is set, `configure_otel` is a no-op and the process
runs with stdout-only logging. This is the supported state for tests and for
local runs that do not have Grafana Cloud credentials.
"""

from __future__ import annotations

import logging
import os
from importlib import metadata as importlib_metadata
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from app.core.settings import Settings

logger = logging.getLogger(__name__)

_TRACER_PROVIDER: Any = None
_LOGGER_PROVIDER: Any = None
_METER_PROVIDER: Any = None
_LOGGING_INSTRUMENTED: bool = False


def configure_otel(settings: Settings) -> None:
    """Install global OTel providers when telemetry is enabled."""
    global _TRACER_PROVIDER, _LOGGER_PROVIDER, _METER_PROVIDER, _LOGGING_INSTRUMENTED

    if not settings.otel_enabled:
        return
    if os.getenv("OTEL_SDK_DISABLED", "").strip().lower() in {"1", "true"}:
        return
    if _TRACER_PROVIDER is not None:
        return

    from opentelemetry import metrics, trace
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": _read_service_version(),
            "deployment.environment.name": settings.app_env,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    _TRACER_PROVIDER = tracer_provider

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    _LOGGER_PROVIDER = logger_provider

    LoggingInstrumentor().instrument(set_logging_format=False)
    _LOGGING_INSTRUMENTED = True

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    _METER_PROVIDER = meter_provider

    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor

    PsycopgInstrumentor().instrument(enable_commenter=True)

    logger.info(
        "otel exporter configured endpoint=%s service_name=%s environment=%s",
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "<unset>"),
        settings.app_name,
        settings.app_env,
        extra={"event_type": "otel.configured"},
    )


def shutdown_otel() -> None:
    """Flush and tear down global OTel providers, if installed."""
    global _TRACER_PROVIDER, _LOGGER_PROVIDER, _METER_PROVIDER, _LOGGING_INSTRUMENTED

    if _LOGGING_INSTRUMENTED:
        try:
            from opentelemetry.instrumentation.logging import LoggingInstrumentor

            LoggingInstrumentor().uninstrument()
        except Exception:
            logger.exception("failed to uninstrument OTel logging instrumentor")
        _LOGGING_INSTRUMENTED = False

    if _METER_PROVIDER is not None:
        try:
            _METER_PROVIDER.shutdown()
        except Exception:
            logger.exception("failed to shut down meter provider")
        _METER_PROVIDER = None

    if _TRACER_PROVIDER is not None:
        try:
            _TRACER_PROVIDER.shutdown()
        except Exception:
            logger.exception("failed to shut down tracer provider")
        _TRACER_PROVIDER = None

    if _LOGGER_PROVIDER is not None:
        try:
            _LOGGER_PROVIDER.shutdown()
        except Exception:
            logger.exception("failed to shut down logger provider")
        _LOGGER_PROVIDER = None


def is_otel_active() -> bool:
    """Return True when OTel providers are currently installed."""
    return _TRACER_PROVIDER is not None


def instrument_database_engine(engine: Engine) -> None:
    """Attach SQLAlchemy span instrumentation with SQL commenter when OTel is active.

    `enable_commenter=True` injects request/trace metadata into SQL comments
    (e.g. `/*traceparent='00-...'*/ SELECT ...`), which surface in PostgreSQL
    server logs and let us correlate slow queries to traces.
    """
    if not is_otel_active():
        return
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().instrument(engine=engine, enable_commenter=True)


def _read_service_version() -> str:
    try:
        return importlib_metadata.version("aptitude-registry")
    except importlib_metadata.PackageNotFoundError:
        return "0.0.0+unknown"
