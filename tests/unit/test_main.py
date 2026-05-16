"""Unit tests for the application entrypoint module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.settings import SETTINGS_ENV_FILE_ENV_VAR, reset_settings_cache
from app.main import STARTUP_BANNER, create_app, run_dev_server
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


@pytest.mark.unit
def test_create_app_tolerates_malformed_dotenv_during_static_wiring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "APP_ENV=prod",
                "AUTH_SERVICE_TOKENS_JSON=[{not-valid-json}]",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(SETTINGS_ENV_FILE_ENV_VAR, str(env_file))
    reset_settings_cache()

    app = create_app()

    assert app.title == "Aptitude Registry Service"
