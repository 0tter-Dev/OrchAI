"""In-memory project repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.projects.ports import (
    ProjectConnectionRepository,
    ProjectRepository,
)
from orchai.domain.identifiers import ProjectId, UserId
from orchai.domain.projects import Project


class ProjectNotFoundError(LookupError):
    """Raised when a project is not present in the repository."""


class InMemoryProjectRepository(ProjectRepository):
    """Simple non-durable project repository."""

    def __init__(self) -> None:
        self._projects: dict[ProjectId, Project] = {}

    async def add(self, project: Project) -> None:
        await self.save(project)

    async def save(self, project: Project) -> None:
        self._projects[project.id] = project

    async def get(self, project_id: ProjectId) -> Project:
        try:
            return self._projects[project_id]
        except KeyError as exc:
            raise ProjectNotFoundError(str(project_id)) from exc

    async def get_by_root_location(self, root_location: str) -> Project | None:
        normalized = root_location.strip()
        for project in self._projects.values():
            if project.root_location == normalized:
                return project
        return None

    async def list(self) -> tuple[Project, ...]:
        return tuple(self._projects.values())


class InMemoryProjectConnectionRepository(ProjectConnectionRepository):
    """Simple non-durable project<->user connection reference store."""

    def __init__(self) -> None:
        self._links: set[tuple[ProjectId, UserId]] = set()

    async def link(self, project_id: ProjectId, user_id: UserId) -> None:
        self._links.add((project_id, user_id))

    async def list_project_ids_for_user(self, user_id: UserId) -> tuple[ProjectId, ...]:
        return tuple(pid for (pid, uid) in self._links if uid == user_id)

    async def list_user_ids_for_project(self, project_id: ProjectId) -> tuple[UserId, ...]:
        return tuple(uid for (pid, uid) in self._links if pid == project_id)
