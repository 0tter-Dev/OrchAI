"""In-memory project repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.projects.ports import ProjectRepository
from orchai.domain.identifiers import ProjectId
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
