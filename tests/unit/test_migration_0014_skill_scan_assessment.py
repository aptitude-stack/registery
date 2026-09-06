"""Unit coverage for Alembic revision 0014."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_migration_module() -> ModuleType:
    module_path = Path("alembic/versions/0014_skill_scan_assessment.py")
    spec = importlib.util.spec_from_file_location(
        "migration_0014_skill_scan_assessment", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_upgrade_adds_nullable_json_assessment(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_migration_module()
    assert module.revision == "0014_skill_scan_assessment"
    assert module.down_revision == "0013_db_structure_cleanup"
    add_column_calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda table_name, column: add_column_calls.append((table_name, column)),
    )

    module.upgrade()

    assert len(add_column_calls) == 1
    table_name, column = add_column_calls[0]
    assert table_name == "skill_versions"
    assert column.name == "assessment"
    assert column.nullable is True
    assert column.server_default is None
    assert "JSONB" in str(column.type)


@pytest.mark.unit
def test_downgrade_drops_assessment(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_migration_module()
    drop_column_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        module.op,
        "drop_column",
        lambda table_name, column_name: drop_column_calls.append((table_name, column_name)),
    )

    module.downgrade()

    assert drop_column_calls == [("skill_versions", "assessment")]
