"""Unit tests for the application entrypoint module."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.main import STARTUP_BANNER, run_dev_server
from app.observability.logging import build_logging_config


@pytest.mark.unit
def test_run_dev_server_prints_banner_and_uses_centralized_logging(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=fake_run))
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "pretty")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("UVICORN_RELOAD", "false")

    run_dev_server()

    stdout = capsys.readouterr().out
    assert STARTUP_BANNER in stdout
    assert captured["app"] == "app.main:app"
    assert captured["kwargs"] == {
        "host": "127.0.0.1",
        "port": 9000,
        "reload": False,
        "log_config": build_logging_config("DEBUG", log_format="pretty", app_env="dev"),
    }
