"""Unit coverage for Alembic revision 0007."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_migration_module() -> ModuleType:
    module_path = Path("alembic/versions/0007_skill_star_counts.py")
    spec = importlib.util.spec_from_file_location("migration_0007_skill_star_counts", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_upgrade_adds_star_count_column(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_migration_module()
    add_column_calls: list[tuple[str, str]] = []

    def record_add_column(table_name: str, column: object) -> None:
        add_column_calls.append((table_name, column.name))

    monkeypatch.setattr(module.op, "add_column", record_add_column)
    module.upgrade()

    assert ("skills", "star_count") in add_column_calls


@pytest.mark.unit
def test_downgrade_drops_star_count_column(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_migration_module()
    drop_column_calls: list[tuple[str, str]] = []

    def record_drop_column(table_name: str, column_name: str) -> None:
        drop_column_calls.append((table_name, column_name))

    monkeypatch.setattr(module.op, "drop_column", record_drop_column)
    module.downgrade()

    assert ("skills", "star_count") in drop_column_calls
