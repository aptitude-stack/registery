"""Unit tests for app.observability.telemetry bootstrap behavior."""

from __future__ import annotations

import pytest

from app.core.settings import Settings, load_settings
from app.observability import telemetry
from tests.unit._otel_helpers import reset_otel_globals


@pytest.fixture(autouse=True)
def _isolate_otel_globals() -> None:
    """OTel SDK global providers are set-once. Reset both module state and
    the SDK private globals around every test so each one starts clean."""
    telemetry.shutdown_otel()
    reset_otel_globals()
    yield
    telemetry.shutdown_otel()
    reset_otel_globals()


def _settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/db")
    monkeypatch.setenv("APP_ENV", overrides.get("APP_ENV", "dev"))
    monkeypatch.setenv("ALLOWED_HOSTS_JSON", overrides.get("ALLOWED_HOSTS_JSON", '["x"]'))
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "1")
    monkeypatch.setenv("OTEL_BSP_EXPORT_TIMEOUT", "500")
    monkeypatch.setenv("OTEL_BSP_SCHEDULE_DELAY", "60000")
    monkeypatch.setenv("OTEL_METRIC_EXPORT_TIMEOUT", "500")
    if "OTEL_ENABLED" in overrides:
        monkeypatch.setenv("OTEL_ENABLED", overrides["OTEL_ENABLED"])
    else:
        monkeypatch.delenv("OTEL_ENABLED", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    if "OTEL_EXPORTER_OTLP_ENDPOINT" in overrides:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", overrides["OTEL_EXPORTER_OTLP_ENDPOINT"])
    if "OTEL_SDK_DISABLED" in overrides:
        monkeypatch.setenv("OTEL_SDK_DISABLED", overrides["OTEL_SDK_DISABLED"])
    return load_settings()


@pytest.mark.unit
def test_configure_otel_is_no_op_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.otel_enabled is False

    telemetry.configure_otel(settings)

    assert telemetry.is_otel_active() is False


@pytest.mark.unit
def test_configure_otel_is_no_op_when_otel_sdk_disabled_env_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        OTEL_ENABLED="true",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318",
        OTEL_SDK_DISABLED="true",
    )

    telemetry.configure_otel(settings)

    assert telemetry.is_otel_active() is False


@pytest.mark.unit
def test_settings_validator_requires_otlp_endpoint_for_prod_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production refuses to boot with OTel enabled but no endpoint configured."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/db")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ALLOWED_HOSTS_JSON", '["api.example"]')
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        load_settings()


@pytest.mark.unit
def test_configure_otel_installs_providers_and_log_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        OTEL_ENABLED="true",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318",
    )

    telemetry.configure_otel(settings)

    assert telemetry.is_otel_active() is True
    assert telemetry._LOGGING_INSTRUMENTED is True


@pytest.mark.unit
def test_shutdown_otel_clears_global_state(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        OTEL_ENABLED="true",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318",
    )
    telemetry.configure_otel(settings)
    assert telemetry.is_otel_active() is True

    telemetry.shutdown_otel()

    assert telemetry.is_otel_active() is False
    assert telemetry._LOGGING_INSTRUMENTED is False


@pytest.mark.unit
def test_instrument_database_engine_is_no_op_without_active_otel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When OTel is disabled the helper must not try to import the SQLAlchemy
    instrumentation package (which would fail without --extra otel)."""
    settings = _settings(monkeypatch)
    assert settings.otel_enabled is False

    class _DummyEngine:
        pass

    telemetry.instrument_database_engine(_DummyEngine())  # type: ignore[arg-type]
