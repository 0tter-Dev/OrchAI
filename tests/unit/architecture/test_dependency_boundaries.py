from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3] / "src" / "orchai"


def test_domain_layer_does_not_import_application_or_infrastructure() -> None:
    violations = _find_forbidden_imports(
        ROOT / "domain",
        forbidden=("orchai.application", "orchai.infrastructure", "orchai.interfaces"),
    )
    assert violations == []


def test_application_layer_does_not_import_interfaces() -> None:
    violations = _find_forbidden_imports(
        ROOT / "application",
        forbidden=("orchai.interfaces",),
    )
    assert violations == []


def _find_forbidden_imports(base: Path, *, forbidden: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in base.rglob("*.py"):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if any(token in stripped for token in forbidden):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}:{stripped}")
    return violations
