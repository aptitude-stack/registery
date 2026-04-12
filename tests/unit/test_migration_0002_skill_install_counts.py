"""Unit coverage for Alembic revision 0002."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_migration_module() -> ModuleType:
    module_path = Path("alembic/versions/0002_skill_install_counts.py")
    spec = importlib.util.spec_from_file_location(
        "migration_0002_skill_install_counts", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_upgrade_adds_install_count_and_removes_legacy_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration_module()
    add_column_calls: list[tuple[str, str]] = []
    drop_column_calls: list[tuple[str, str]] = []

    def record_add_column(table_name: str, column: object) -> None:
        add_column_calls.append((table_name, column.name))

    def record_drop_column(table_name: str, column_name: str) -> None:
        drop_column_calls.append((table_name, column_name))

    monkeypatch.setattr(module.op, "add_column", record_add_column)
    monkeypatch.setattr(module.op, "drop_column", record_drop_column)

    module.upgrade()

    assert ("skills", "install_count") in add_column_calls
    assert ("skill_metadata", "headers") in drop_column_calls


@pytest.mark.unit
def test_downgrade_restores_legacy_headers_and_removes_install_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration_module()
    add_column_calls: list[tuple[str, str]] = []
    drop_column_calls: list[tuple[str, str]] = []

    def record_add_column(table_name: str, column: object) -> None:
        add_column_calls.append((table_name, column.name))

    def record_drop_column(table_name: str, column_name: str) -> None:
        drop_column_calls.append((table_name, column_name))

    monkeypatch.setattr(module.op, "add_column", record_add_column)
    monkeypatch.setattr(module.op, "drop_column", record_drop_column)

    module.downgrade()

    assert ("skill_metadata", "headers") in add_column_calls
    assert ("skills", "install_count") in drop_column_calls
