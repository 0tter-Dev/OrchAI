import asyncio

import pytest

from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextReference, ContextSource
from orchai.domain.projects import PersistenceClassification, ProviderSharingLevel
from orchai.infrastructure.projects import MediaWorkspaceProjectAdapter
from orchai.infrastructure.projects.errors import (
    ProjectCapabilityError,
    ProjectResourceAccessError,
)


def test_media_workspace_adapter_discovers_and_classifies_media_types(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / "notes.md").write_text("# Plan", encoding="utf-8")
        (tmp_path / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("ignored", encoding="utf-8")
        adapter = MediaWorkspaceProjectAdapter(tmp_path)

        discovery = await adapter.discover(limit=10)

        resources = {resource.resource: resource for resource in discovery.resources}
        assert set(resources) == {"notes.md", "cover.png"}
        assert resources["notes.md"].metadata["media_type"] == "text"
        assert resources["cover.png"].metadata["media_type"] == "image"

    asyncio.run(run())


def test_media_workspace_adapter_reads_text_files_as_content(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / "brief.md").write_text("Make it blue.", encoding="utf-8")
        adapter = MediaWorkspaceProjectAdapter(tmp_path)

        item = await adapter.read_context(
            ContextReference(source=ContextSource.SOURCE_FILE, resource="brief.md")
        )

        assert item.content == "Make it blue."
        assert item.metadata["media_type"] == "text"

    asyncio.run(run())


def test_media_workspace_adapter_describes_binary_files_instead_of_decoding_them(
    tmp_path,
) -> None:
    async def run() -> None:
        (tmp_path / "cover.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
        adapter = MediaWorkspaceProjectAdapter(tmp_path)

        item = await adapter.read_context(
            ContextReference(source=ContextSource.SOURCE_FILE, resource="cover.png")
        )

        assert "image file" in item.content
        assert "binary content not inlined" in item.content
        assert item.metadata["media_type"] == "image"

    asyncio.run(run())


def test_media_workspace_adapter_rejects_path_escape(tmp_path) -> None:
    async def run() -> None:
        adapter = MediaWorkspaceProjectAdapter(tmp_path)

        with pytest.raises(ProjectResourceAccessError):
            await adapter.read_context(
                ContextReference(source=ContextSource.SOURCE_FILE, resource="../outside.png")
            )

    asyncio.run(run())


def test_media_workspace_adapter_classifies_sensitive_resources(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")
        adapter = MediaWorkspaceProjectAdapter(tmp_path)

        resource = await adapter.classify_resource(
            ContextReference(source=ContextSource.SOURCE_FILE, resource=".env")
        )

        assert resource.restricted is True
        assert resource.provider_sharing_level is ProviderSharingLevel.NEVER_EXTERNALIZED
        assert (
            resource.persistence_classification
            is PersistenceClassification.DISALLOWED_BY_DEFAULT
        )

    asyncio.run(run())


def test_media_workspace_adapter_writes_a_generated_asset(tmp_path) -> None:
    async def run() -> None:
        adapter = MediaWorkspaceProjectAdapter(tmp_path)

        result = await adapter.write(
            ContextReference(source=ContextSource.SOURCE_FILE, resource="drafts/idea.txt"),
            "A sunset over mountains.",
        )

        assert result.resource == "drafts/idea.txt"
        assert (tmp_path / "drafts" / "idea.txt").read_text(encoding="utf-8") == (
            "A sunset over mountains."
        )

    asyncio.run(run())


def test_media_workspace_adapter_blocks_write_without_capability(tmp_path) -> None:
    async def run() -> None:
        adapter = MediaWorkspaceProjectAdapter(
            tmp_path,
            exposed_capabilities=frozenset({CapabilityName.READ_PROJECT}),
        )

        with pytest.raises(ProjectCapabilityError):
            await adapter.write(
                ContextReference(source=ContextSource.SOURCE_FILE, resource="idea.txt"),
                "content",
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "method_name,args",
    [
        ("run_tests", {}),
        ("run_command", {"command": ("echo", "hi")}),
        ("git_status", {}),
        ("write_documentation", {"reference": None, "content": "x"}),
    ],
)
def test_media_workspace_adapter_never_exposes_code_repository_capabilities(
    tmp_path, method_name, args
) -> None:
    async def run() -> None:
        adapter = MediaWorkspaceProjectAdapter(tmp_path)
        method = getattr(adapter, method_name)
        call_args = dict(args)
        if call_args.get("reference", "unset") is None:
            call_args["reference"] = ContextReference(
                source=ContextSource.SOURCE_FILE, resource="idea.txt"
            )

        with pytest.raises(ProjectCapabilityError):
            await method(**call_args)

    asyncio.run(run())


def test_media_workspace_adapter_readiness_reflects_write_capability(tmp_path) -> None:
    async def run() -> None:
        writable = MediaWorkspaceProjectAdapter(tmp_path)
        read_only = MediaWorkspaceProjectAdapter(
            tmp_path,
            exposed_capabilities=frozenset({CapabilityName.READ_PROJECT}),
        )

        writable_readiness = await writable.assess_readiness()
        read_only_readiness = await read_only.assess_readiness()

        assert writable_readiness.readiness_level.value == "LEVEL_1_CHANGEABLE"
        assert read_only_readiness.readiness_level.value == "LEVEL_0_CONNECTABLE"

    asyncio.run(run())
