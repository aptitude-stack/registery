"""Unit coverage for Alembic revision 0011."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_migration_module() -> ModuleType:
    module_path = Path("alembic/versions/0011_skill_metadata_overall_score.py")
    spec = importlib.util.spec_from_file_location("migration_0011_overall_score", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_upgrade_adds_nullable_overall_score_and_range_constraint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration_module()
    assert module.revision == "0011_overall_score"
    add_column_calls: list[tuple[str, object]] = []
    check_constraint_calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda table_name, column: add_column_calls.append((table_name, column)),
    )
    monkeypatch.setattr(
        module.op,
        "create_check_constraint",
        lambda name, table_name, condition: check_constraint_calls.append(
            (name, table_name, condition)
        ),
    )

    module.upgrade()

    assert len(add_column_calls) == 1
    table_name, column = add_column_calls[0]
    assert table_name == "skill_metadata"
    assert column.name == "overall_score"
    assert column.nullable is True
    assert column.server_default is None
    assert check_constraint_calls == [
        (
            "ck_skill_metadata_overall_score_range",
            "skill_metadata",
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 1)",
        )
    ]


@pytest.mark.unit
def test_downgrade_drops_overall_score_constraint_and_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_migration_module()
    drop_constraint_calls: list[tuple[str, str]] = []
    drop_column_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        module.op,
        "drop_constraint",
        lambda name, table_name, type_: drop_constraint_calls.append((name, table_name)),
    )
    monkeypatch.setattr(
        module.op,
        "drop_column",
        lambda table_name, column_name: drop_column_calls.append((table_name, column_name)),
    )

    module.downgrade()

    assert drop_constraint_calls == [("ck_skill_metadata_overall_score_range", "skill_metadata")]
    assert drop_column_calls == [("skill_metadata", "overall_score")]
