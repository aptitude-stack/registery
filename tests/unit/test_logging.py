"""Unit tests for centralized logging configuration."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest

from app.observability.context import clear_request_context, set_request_context
from app.observability.logging import build_logging_config, configure_logging


def _app_handler() -> logging.Handler:
    return logging.getLogger("app").handlers[0]


@contextmanager
def _captured_handler_stream() -> Iterator[StringIO]:
    handler = _app_handler()
    original_stream = handler.stream
    stream = StringIO()
    handler.setStream(stream)
    try:
        yield stream
    finally:
        handler.setStream(original_stream)


@pytest.mark.unit
def test_build_logging_config_uses_shared_format_for_app_and_libraries() -> None:
    config = build_logging_config("INFO", log_format="json", app_env="prod", interactive=False)

    assert config["formatters"]["default"]["()"] == "app.observability.logging.JsonLogFormatter"
    assert config["handlers"]["default"]["stream"] == "ext://sys.stdout"
    assert config["root"]["level"] == logging.INFO
    assert config["loggers"]["app"]["handlers"] == ["default"]
    assert config["loggers"]["app"]["level"] == logging.INFO
    assert config["loggers"]["uvicorn.error"]["handlers"] == ["default"]
    assert config["loggers"]["uvicorn.error"]["propagate"] is False
    assert config["loggers"]["uvicorn.access"]["level"] == logging.INFO
    assert config["loggers"]["uvicorn.access"]["propagate"] is False
    assert config["loggers"]["watchfiles"]["level"] == logging.WARNING
    assert config["loggers"]["sqlalchemy"]["handlers"] == ["default"]
    assert config["loggers"]["sqlalchemy"]["level"] == logging.WARNING
    assert config["loggers"]["psycopg"]["handlers"] == ["default"]
    assert config["loggers"]["psycopg"]["level"] == logging.WARNING


@pytest.mark.unit
def test_configure_logging_wires_root_and_library_loggers_to_stdout() -> None:
    configure_logging("invalid-level", log_format="json", app_env="prod", interactive=False)

    root_logger = logging.getLogger()
    app_logger = logging.getLogger("app.main")
    uvicorn_error_logger = logging.getLogger("uvicorn.error")

    assert root_logger.level == logging.INFO
    assert app_logger.level == logging.NOTSET
    assert uvicorn_error_logger.level == logging.INFO
    assert uvicorn_error_logger.propagate is False
    assert app_logger.parent is logging.getLogger("app")
    assert root_logger.handlers[0].stream is sys.stdout
    assert root_logger.handlers[0].formatter is not None
    assert root_logger.handlers[0].formatter.__class__.__name__ == "JsonLogFormatter"
    assert uvicorn_error_logger.handlers[0].stream is sys.stdout
    assert uvicorn_error_logger.handlers[0].formatter is not None
    assert uvicorn_error_logger.handlers[0].formatter.__class__.__name__ == "JsonLogFormatter"


@pytest.mark.unit
def test_build_logging_config_keeps_noisy_libraries_verbose_in_debug() -> None:
    config = build_logging_config("DEBUG", log_format="json", app_env="prod", interactive=False)

    assert config["loggers"]["uvicorn.access"]["level"] == logging.DEBUG
    assert config["loggers"]["watchfiles"]["level"] == logging.DEBUG
    assert config["loggers"]["sqlalchemy"]["level"] == logging.DEBUG
    assert config["loggers"]["psycopg"]["level"] == logging.DEBUG


@pytest.mark.unit
def test_build_logging_config_uses_pretty_formatter_when_requested() -> None:
    config = build_logging_config("INFO", log_format="pretty", app_env="dev", interactive=True)

    assert config["formatters"]["default"]["()"] == "app.observability.logging.PrettyLogFormatter"


@pytest.mark.unit
def test_build_logging_config_auto_uses_pretty_for_local_interactive_runs() -> None:
    config = build_logging_config("INFO", log_format="auto", app_env="dev", interactive=True)

    assert config["formatters"]["default"]["()"] == "app.observability.logging.PrettyLogFormatter"


@pytest.mark.unit
def test_build_logging_config_auto_uses_json_for_prod_runs() -> None:
    config = build_logging_config("INFO", log_format="auto", app_env="prod", interactive=True)

    assert config["formatters"]["default"]["()"] == "app.observability.logging.JsonLogFormatter"


@pytest.mark.unit
def test_build_logging_config_auto_uses_json_for_non_interactive_runs() -> None:
    config = build_logging_config("INFO", log_format="auto", app_env="dev", interactive=False)

    assert config["formatters"]["default"]["()"] == "app.observability.logging.JsonLogFormatter"


@pytest.mark.unit
def test_build_logging_config_adds_json_file_handler_when_log_file_path_is_set() -> None:
    config = build_logging_config(
        "INFO",
        log_format="pretty",
        app_env="dev",
        interactive=True,
        log_file_path="/tmp/aptitude/app.jsonl",
    )

    assert config["formatters"]["default"]["()"] == "app.observability.logging.PrettyLogFormatter"
    assert config["formatters"]["json"]["()"] == "app.observability.logging.JsonLogFormatter"
    assert config["handlers"]["file"]["class"] == "logging.FileHandler"
    assert config["handlers"]["file"]["formatter"] == "json"
    assert config["handlers"]["file"]["filename"] == "/tmp/aptitude/app.jsonl"
    assert config["root"]["handlers"] == ["default", "file"]
    assert config["loggers"]["app"]["handlers"] == ["default", "file"]
    assert config["loggers"]["uvicorn.error"]["handlers"] == ["default", "file"]
    assert config["loggers"]["uvicorn.access"]["handlers"] == ["default"]


@pytest.mark.unit
def test_configured_logger_emits_json_with_request_context() -> None:
    configure_logging("INFO", log_format="json", app_env="prod", interactive=False)
    set_request_context(
        request_id="req-123",
        http_method="GET",
        http_route="/healthz",
        status_code=200,
        duration_ms=12.5,
        client_ip="127.0.0.1",
        user_agent="pytest-agent",
        surface="system",
        outcome="success",
    )
    logger = logging.getLogger("app.main")

    try:
        with _captured_handler_stream() as stream:
            logger.info("request complete", extra={"event_type": "request.completed"})
    finally:
        clear_request_context()

    output = stream.getvalue().strip()
    payload = json.loads(output)

    assert payload["message"] == "request complete"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.main"
    assert payload["request_id"] == "req-123"
    assert payload["http_method"] == "GET"
    assert payload["http_route"] == "/healthz"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5
    assert payload["client_ip"] == "127.0.0.1"
    assert payload["user_agent"] == "pytest-agent"
    assert payload["surface"] == "system"
    assert payload["outcome"] == "success"
    assert payload["event_type"] == "request.completed"
    assert "timestamp" in payload


@pytest.mark.unit
def test_configured_logger_emits_pretty_human_readable_output() -> None:
    configure_logging("INFO", log_format="pretty", app_env="dev", interactive=True)
    set_request_context(
        request_id="req-456",
        http_method="GET",
        http_route="/healthz",
        status_code=200,
        duration_ms=1.3,
        surface="system",
        outcome="success",
        error_code="AUTHENTICATION_REQUIRED",
        exception_type="ApiError",
    )
    logger = logging.getLogger("app.main")

    try:
        with _captured_handler_stream() as stream:
            logger.info("request complete", extra={"event_type": "request.completed"})
    finally:
        clear_request_context()

    output = stream.getvalue().strip()

    assert "INFO" in output
    assert "app.main" in output
    assert "request complete" in output
    assert "method=GET" in output
    assert "route=/healthz" in output
    assert "status=200" in output
    assert "duration_ms=1.3" in output
    assert "request_id=req-456" in output
    assert "surface=system" in output
    assert "outcome=success" in output
    assert "error_code=AUTHENTICATION_REQUIRED" in output
    assert "exception_type=ApiError" in output
    assert output.startswith("20")


@pytest.mark.unit
def test_configured_logger_writes_json_to_file_handler(
    tmp_path: Path,
) -> None:
    log_file_path = tmp_path / "app.jsonl"
    configure_logging(
        "INFO",
        log_format="pretty",
        app_env="dev",
        interactive=True,
        log_file_path=str(log_file_path),
    )
    set_request_context(
        request_id="req-file",
        http_method="GET",
        http_route="/healthz",
        status_code=200,
        duration_ms=2.5,
        surface="system",
        outcome="success",
    )
    logger = logging.getLogger("app.main")

    try:
        logger.info("file sink log", extra={"event_type": "request.completed"})
    finally:
        clear_request_context()

    payload = json.loads(log_file_path.read_text().strip())

    assert payload["message"] == "file sink log"
    assert payload["request_id"] == "req-file"
    assert payload["http_route"] == "/healthz"
    assert payload["surface"] == "system"
    assert payload["outcome"] == "success"
    assert payload["event_type"] == "request.completed"


@pytest.mark.unit
def test_uvicorn_access_logger_does_not_write_to_file_handler(
    tmp_path: Path,
) -> None:
    log_file_path = tmp_path / "app.jsonl"
    configure_logging(
        "INFO",
        log_format="pretty",
        app_env="dev",
        interactive=True,
        log_file_path=str(log_file_path),
    )

    logging.getLogger("uvicorn.access").info('127.0.0.1:12345 - "GET /healthz HTTP/1.1" 200')

    assert not log_file_path.exists() or log_file_path.read_text() == ""


@pytest.mark.unit
def test_configure_logging_rebinds_stdout_handler_when_stream_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_stdout = StringIO()
    second_stdout = StringIO()

    monkeypatch.setattr(sys, "stdout", first_stdout)
    configure_logging("INFO", log_format="json", app_env="prod", interactive=False)
    assert _app_handler().stream is first_stdout
    logging.getLogger("app.main").info("first log")

    monkeypatch.setattr(sys, "stdout", second_stdout)
    configure_logging("INFO", log_format="json", app_env="prod", interactive=False)
    assert _app_handler().stream is second_stdout
    logging.getLogger("app.main").info("second log")

    assert "first log" in first_stdout.getvalue()
    assert "second log" not in first_stdout.getvalue()
    assert "second log" in second_stdout.getvalue()


@pytest.mark.unit
def test_configure_logging_resets_descendant_logger_state() -> None:
    stale_logger = logging.getLogger("app.main")
    stale_logger.handlers = [logging.NullHandler()]
    stale_logger.propagate = False
    stale_logger.setLevel(logging.ERROR)

    configure_logging("INFO", log_format="json", app_env="prod", interactive=False)

    assert stale_logger.handlers == []
    assert stale_logger.propagate is True
    assert stale_logger.level == logging.NOTSET

    with _captured_handler_stream() as stream:
        stale_logger.info("descendant logger recovered")

    assert "descendant logger recovered" in stream.getvalue()
