import asyncio

import pytest

from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextReference, ContextSource
from orchai.domain.projects import (
    PersistenceClassification,
    ProviderSharingLevel,
)
from orchai.infrastructure.projects import LocalFilesystemProjectAdapter
from orchai.infrastructure.projects.errors import (
    ProjectCapabilityError,
    ProjectResourceAccessError,
)


def test_local_filesystem_adapter_resolves_relative_context(tmp_path) -> None:
    async def run() -> None:
        source = tmp_path / "src"
        source.mkdir()
        file_path = source / "app.py"
        file_path.write_text("print('hello')", encoding="utf-8")
        adapter = LocalFilesystemProjectAdapter(tmp_path)

        items = await adapter.resolve_context(
            (
                ContextReference(
                    source=ContextSource.SOURCE_FILE,
                    resource="src/app.py",
                ),
            )
        )

        assert len(items) == 1
        assert items[0].content == "print('hello')"

    asyncio.run(run())


def test_local_filesystem_adapter_rejects_path_escape(tmp_path) -> None:
    async def run() -> None:
        adapter = LocalFilesystemProjectAdapter(
            tmp_path,
            exposed_capabilities=frozenset({CapabilityName.READ_PROJECT}),
        )

        with pytest.raises(ProjectResourceAccessError):
            await adapter.resolve_context(
                (
                    ContextReference(
                        source=ContextSource.SOURCE_FILE,
                        resource="../outside.txt",
                    ),
                )
            )

    asyncio.run(run())


def test_local_filesystem_adapter_discovers_resource_metadata(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
        source = tmp_path / "src"
        source.mkdir()
        (source / "app.py").write_text("print('hello')", encoding="utf-8")
        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("ignored", encoding="utf-8")
        adapter = LocalFilesystemProjectAdapter(tmp_path)

        discovery = await adapter.discover(limit=10)

        resources = {resource.resource: resource for resource in discovery.resources}
        assert set(resources) == {"README.md", "src/app.py"}
        assert resources["README.md"].source is ContextSource.PROJECT_DOCUMENTATION
        assert resources["src/app.py"].source is ContextSource.SOURCE_FILE

    asyncio.run(run())


def test_local_filesystem_adapter_assesses_readiness_levels(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_smoke.py").write_text("def test_ok(): pass", encoding="utf-8")
        adapter = LocalFilesystemProjectAdapter(tmp_path)

        readiness = await adapter.assess_readiness()

        assert readiness.readiness_level.value == "LEVEL_3_AUTOMATABLE"
        assert readiness.has_git is True
        assert readiness.has_documentation is True
        assert readiness.has_tests is True

    asyncio.run(run())


def test_local_filesystem_adapter_classifies_sensitive_resources(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")
        adapter = LocalFilesystemProjectAdapter(
            tmp_path,
            exposed_capabilities=frozenset({CapabilityName.READ_PROJECT}),
        )

        resource = await adapter.classify_resource(
            ContextReference(
                source=ContextSource.SOURCE_FILE,
                resource=".env",
            )
        )

        assert resource.restricted is True
        assert resource.provider_sharing_level is ProviderSharingLevel.NEVER_EXTERNALIZED
        assert (
            resource.persistence_classification
            is PersistenceClassification.DISALLOWED_BY_DEFAULT
        )

    asyncio.run(run())


def test_local_filesystem_adapter_blocks_write_without_capability(tmp_path) -> None:
    async def run() -> None:
        adapter = LocalFilesystemProjectAdapter(
            tmp_path,
            exposed_capabilities=frozenset({CapabilityName.READ_PROJECT}),
        )
        with pytest.raises(ProjectCapabilityError):
            await adapter.write(
                ContextReference(
                    source=ContextSource.SOURCE_FILE,
                    resource="src/app.py",
                ),
                "print('hello')",
            )

    asyncio.run(run())


def test_local_filesystem_adapter_writes_when_capability_is_present(tmp_path) -> None:
    async def run() -> None:
        adapter = LocalFilesystemProjectAdapter(
            tmp_path,
            exposed_capabilities=frozenset({CapabilityName.WRITE_SOURCE}),
        )
        result = await adapter.write(
            ContextReference(
                source=ContextSource.SOURCE_FILE,
                resource="src/app.py",
            ),
            "print('hello')",
        )

        assert result.resource == "src/app.py"
        assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "print('hello')"

    asyncio.run(run())
