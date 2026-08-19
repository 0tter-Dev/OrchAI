import asyncio

import pytest

from orchai.domain.context import ContextReference, ContextSource
from orchai.infrastructure.projects import LocalFilesystemProjectAdapter
from orchai.infrastructure.projects.errors import ProjectResourceAccessError


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
        adapter = LocalFilesystemProjectAdapter(tmp_path)

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
