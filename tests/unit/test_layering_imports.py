"""Architecture guardrails for module dependency direction."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORT_RULES = (
    (REPO_ROOT / "app" / "interface", "app.persistence"),
    (REPO_ROOT / "app" / "core", "app.persistence"),
    (REPO_ROOT / "app" / "core", "fastapi"),
    (REPO_ROOT / "app" / "core", "starlette"),
    (REPO_ROOT / "app" / "core", "app.interface"),
)


def _iter_python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _iter_imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.lineno, node.module))

    return imports


@pytest.mark.unit
def test_layering_forbids_core_framework_and_adapter_imports() -> None:
    violations: list[str] = []

    for package_root, forbidden_prefix in FORBIDDEN_IMPORT_RULES:
        for path in _iter_python_files(package_root):
            for line, imported_module in _iter_imports(path):
                if imported_module.startswith(forbidden_prefix):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{line} imports {imported_module}",
                    )

    assert not violations, "Layering violations found:\n" + "\n".join(violations)
