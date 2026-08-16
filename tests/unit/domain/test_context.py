import pytest

from orchai.domain.context import ContextItem, ContextPackage, ContextReference
from orchai.domain.context.sources import ContextSource
from orchai.domain.identifiers import ExecutionId, ProjectId


def test_context_reference_normalizes_text_fields() -> None:
    reference = ContextReference(
        source=ContextSource.SOURCE_FILE,
        resource=" src/orchai/__init__.py ",
        scope=" ",
        version=" main ",
    )

    assert reference.resource == "src/orchai/__init__.py"
    assert reference.scope is None
    assert reference.version == "main"


def test_context_package_rejects_items_outside_authorized_references() -> None:
    authorized = ContextReference(
        source=ContextSource.SOURCE_FILE,
        resource="allowed.py",
    )
    unauthorized = ContextReference(
        source=ContextSource.SOURCE_FILE,
        resource="secret.py",
    )

    with pytest.raises(ValueError):
        ContextPackage(
            execution_id=ExecutionId.new(),
            project_id=ProjectId.new(),
            requested_references=(authorized, unauthorized),
            authorized_references=(authorized,),
            items=(ContextItem(reference=unauthorized, content="secret"),),
        )

