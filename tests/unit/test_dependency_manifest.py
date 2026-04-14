"""Regression tests for runtime vs development dependency boundaries."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_runtime_dependencies_exclude_dev_only_tools_and_include_bundle_support() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    runtime_dependencies = pyproject["project"]["dependencies"]
    development_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert not any(dependency.startswith("pytest") for dependency in runtime_dependencies)
    assert not any(dependency.startswith("mypy") for dependency in runtime_dependencies)
    assert any(dependency.startswith("zstandard") for dependency in runtime_dependencies)
    assert any(dependency.startswith("pytest") for dependency in development_dependencies)
    assert any(dependency.startswith("mypy") for dependency in development_dependencies)
