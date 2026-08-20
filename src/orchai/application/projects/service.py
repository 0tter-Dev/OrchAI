"""Project application service."""

from __future__ import annotations

from orchai.application.events.ports import EventPublisher
from orchai.application.projects.commands import (
    RegisterProjectCommand,
    UpdateProjectSecurityCommand,
)
from orchai.application.projects.ports import ProjectRepository
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import Project
from orchai.domain.projects.security import ProjectSecurityProfile


class ProjectService:
    """Coordinates project metadata without owning project content."""

    def __init__(
        self,
        *,
        repository: ProjectRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    async def register_project(self, command: RegisterProjectCommand) -> Project:
        observed_readiness_level = (
            command.observed_readiness_level or command.readiness_level
        )
        observed_security_profile = (
            command.observed_security_profile or command.security_profile
        )
        existing = await self._repository.get_by_root_location(command.root_location)
        if existing is not None:
            project = Project(
                id=existing.id,
                name=command.name,
                root_location=command.root_location,
                adapter_type=command.adapter_type,
                capabilities=frozenset(command.capabilities),
                status=existing.status,
                readiness_level=existing.readiness_level,
                security_profile=existing.security_profile,
                observed_readiness_level=observed_readiness_level,
                observed_security_profile=observed_security_profile,
            )
            await self._repository.save(project)
            return project

        project = Project(
            name=command.name,
            root_location=command.root_location,
            adapter_type=command.adapter_type,
            capabilities=frozenset(command.capabilities),
            readiness_level=command.readiness_level,
            security_profile=command.security_profile,
            observed_readiness_level=observed_readiness_level,
            observed_security_profile=observed_security_profile,
        )
        await self._repository.add(project)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_REGISTERED,
                source="application.projects",
                project_id=project.id,
                payload={
                    "project_id": str(project.id),
                    "name": project.name,
                    "adapter_type": project.adapter_type,
                    "readiness_level": project.readiness_level.value,
                    "observed_readiness_level": project.observed_readiness_level.value,
                },
            )
        )
        return project

    async def get_project(self, project_id: ProjectId) -> Project:
        return await self._repository.get(project_id)

    async def list_projects(self) -> tuple[Project, ...]:
        return await self._repository.list()

    async def update_security_profile(
        self,
        command: UpdateProjectSecurityCommand,
    ) -> Project:
        project = await self._repository.get(command.project_id)
        profile = project.security_profile
        readiness_level = command.readiness_level or project.readiness_level
        updated_profile = ProjectSecurityProfile(
            readiness_level=readiness_level,
            access_scope=(
                command.access_scope
                if command.access_scope is not None
                else profile.access_scope
            ),
            restricted_areas=(
                command.restricted_areas
                if command.restricted_areas is not None
                else profile.restricted_areas
            ),
            sensitive_patterns=(
                command.sensitive_patterns
                if command.sensitive_patterns is not None
                else profile.sensitive_patterns
            ),
            allow_git_bootstrap=(
                command.allow_git_bootstrap
                if command.allow_git_bootstrap is not None
                else profile.allow_git_bootstrap
            ),
            allow_architecture_restructure=(
                command.allow_architecture_restructure
                if command.allow_architecture_restructure is not None
                else profile.allow_architecture_restructure
            ),
            allow_cicd_changes=(
                command.allow_cicd_changes
                if command.allow_cicd_changes is not None
                else profile.allow_cicd_changes
            ),
            allow_cloud_provider_sharing=(
                command.allow_cloud_provider_sharing
                if command.allow_cloud_provider_sharing is not None
                else profile.allow_cloud_provider_sharing
            ),
            persist_architecture_summaries=(
                command.persist_architecture_summaries
                if command.persist_architecture_summaries is not None
                else profile.persist_architecture_summaries
            ),
            persist_naming_summaries=(
                command.persist_naming_summaries
                if command.persist_naming_summaries is not None
                else profile.persist_naming_summaries
            ),
            persist_functional_summaries=(
                command.persist_functional_summaries
                if command.persist_functional_summaries is not None
                else profile.persist_functional_summaries
            ),
            persist_context_snapshots=(
                command.persist_context_snapshots
                if command.persist_context_snapshots is not None
                else profile.persist_context_snapshots
            ),
            metadata=command.metadata if command.metadata is not None else profile.metadata,
        )
        updated_project = Project(
            id=project.id,
            name=project.name,
            root_location=project.root_location,
            adapter_type=project.adapter_type,
            capabilities=project.capabilities,
            status=project.status,
            readiness_level=readiness_level,
            security_profile=updated_profile,
            observed_readiness_level=project.observed_readiness_level,
            observed_security_profile=project.observed_security_profile,
        )
        await self._repository.save(updated_project)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_SECURITY_PROFILE_UPDATED,
                source="application.projects",
                project_id=updated_project.id,
                payload={
                    "project_id": str(updated_project.id),
                    "readiness_level": updated_project.readiness_level.value,
                    "observed_readiness_level": (
                        updated_project.observed_readiness_level.value
                    ),
                    "allow_cloud_provider_sharing": str(
                        updated_project.security_profile.allow_cloud_provider_sharing
                    ),
                    "allow_git_bootstrap": str(
                        updated_project.security_profile.allow_git_bootstrap
                    ),
                    "allow_architecture_restructure": str(
                        updated_project.security_profile.allow_architecture_restructure
                    ),
                    "allow_cicd_changes": str(
                        updated_project.security_profile.allow_cicd_changes
                    ),
                },
            )
        )
        return updated_project
