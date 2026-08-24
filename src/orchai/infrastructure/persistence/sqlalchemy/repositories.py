"""SQLAlchemy repository implementations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from orchai.application.audit.ports import AuditRepository
from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.context.ports import ContextResolutionRepository
from orchai.application.events.ports import EventRepository
from orchai.application.executions.ports import ExecutionRepository
from orchai.application.identity.ports import (
    AccessControlRepository,
    AccessRoleRepository,
)
from orchai.application.identity.ports import (
    PermissionRepository as IdentityPermissionRepository,
)
from orchai.application.identity.ports import (
    RefreshTokenRepository as IdentityRefreshTokenRepository,
)
from orchai.application.identity.ports import (
    UserRepository as IdentityUserRepository,
)
from orchai.application.metrics.ports import MetricsRepository
from orchai.application.projects.ports import (
    ProjectConnectionRepository,
    ProjectRepository,
)
from orchai.application.suggestions.ports import SuggestionRepository
from orchai.application.tasks.ports import TaskRepository
from orchai.domain.actions import ActionName
from orchai.domain.audit import AuditRecord
from orchai.domain.authorization import (
    Authorization,
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationRequest,
    RequestedOperation,
)
from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import (
    ContextReference,
    ContextResolutionRecord,
    ContextSource,
)
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.executions import (
    Execution,
    ExecutionResult,
    ExecutionState,
    ResourceUsage,
)
from orchai.domain.identifiers import (
    AccessRoleId,
    AuditRecordId,
    AuthorizationDecisionId,
    AuthorizationId,
    CausationId,
    ContextResolutionId,
    CorrelationId,
    EventId,
    ExecutionId,
    MetricRecordId,
    ModelId,
    PermissionId,
    ProjectId,
    RefreshTokenId,
    SuggestionId,
    TaskId,
    UserId,
)
from orchai.domain.identity import AccessRole, Permission, RefreshToken, User
from orchai.domain.metrics import MetricRecord
from orchai.domain.projects import (
    Project,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProjectStatus,
)
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.domain.tasks import ExecutionMode, Task, TaskScope, TaskState
from orchai.infrastructure.persistence.sqlalchemy.database import SQLAlchemyDatabase
from orchai.infrastructure.persistence.sqlalchemy.tables import (
    access_roles_table,
    audit_records_table,
    authorization_decisions_table,
    authorization_requests_table,
    context_resolution_records_table,
    events_table,
    executions_table,
    metric_records_table,
    permissions_table,
    project_connections_table,
    projects_table,
    refresh_tokens_table,
    role_permissions_table,
    suggestions_table,
    tasks_table,
    user_permissions_table,
    user_roles_table,
    users_table,
)


class SQLAlchemyTaskRepository(TaskRepository):
    """SQLAlchemy-backed task repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, task: Task) -> None:
        await self.save(task)

    async def get(self, task_id: TaskId) -> Task:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(tasks_table).where(tasks_table.c.id == str(task_id))
            ).first()
        if row is None:
            raise LookupError(str(task_id))
        return _task_from_row(row._mapping)

    async def save(self, task: Task) -> None:
        values = _task_to_values(task)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(tasks_table.c.id).where(tasks_table.c.id == values["id"])
            ).first()
            if exists is None:
                connection.execute(insert(tasks_table).values(**values))
            else:
                connection.execute(
                    update(tasks_table)
                    .where(tasks_table.c.id == values["id"])
                    .values(**values)
                )

    async def list(
        self,
        *,
        project_id: ProjectId | None = None,
        state: TaskState | None = None,
        limit: int = 20,
    ) -> tuple[Task, ...]:
        query = select(tasks_table).order_by(tasks_table.c.id.desc())
        if project_id is not None:
            query = query.where(tasks_table.c.project_id == str(project_id))
        if state is not None:
            query = query.where(tasks_table.c.state == state.value)
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_task_from_row(row._mapping) for row in rows)


class SQLAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy-backed project repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, project: Project) -> None:
        await self.save(project)

    async def save(self, project: Project) -> None:
        values = _project_to_values(project)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(projects_table.c.id).where(projects_table.c.id == values["id"])
            ).first()
            if exists is None:
                connection.execute(insert(projects_table).values(**values))
            else:
                connection.execute(
                    update(projects_table)
                    .where(projects_table.c.id == values["id"])
                    .values(**values)
                )

    async def get(self, project_id: ProjectId) -> Project:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(projects_table).where(projects_table.c.id == str(project_id))
            ).first()
        if row is None:
            raise LookupError(str(project_id))
        return _project_from_row(row._mapping)

    async def get_by_root_location(self, root_location: str) -> Project | None:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(projects_table).where(
                    projects_table.c.root_location == root_location.strip()
                )
            ).first()
        if row is None:
            return None
        return _project_from_row(row._mapping)

    async def list(self) -> tuple[Project, ...]:
        query = select(projects_table).order_by(projects_table.c.name.asc())
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_project_from_row(row._mapping) for row in rows)


class SQLAlchemyProjectConnectionRepository(ProjectConnectionRepository):
    """SQLAlchemy-backed project<->user connection reference store."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def link(self, project_id: ProjectId, user_id: UserId) -> None:
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(project_connections_table.c.project_id).where(
                    project_connections_table.c.project_id == str(project_id),
                    project_connections_table.c.user_id == str(user_id),
                )
            ).first()
            if exists is None:
                connection.execute(
                    insert(project_connections_table).values(
                        project_id=str(project_id),
                        user_id=str(user_id),
                        connected_at=datetime.now(UTC).isoformat(),
                    )
                )

    async def list_project_ids_for_user(self, user_id: UserId) -> tuple[ProjectId, ...]:
        with self._database.engine.begin() as connection:
            rows = connection.execute(
                select(project_connections_table.c.project_id).where(
                    project_connections_table.c.user_id == str(user_id)
                )
            ).all()
        return tuple(ProjectId(row._mapping["project_id"]) for row in rows)

    async def list_user_ids_for_project(self, project_id: ProjectId) -> tuple[UserId, ...]:
        with self._database.engine.begin() as connection:
            rows = connection.execute(
                select(project_connections_table.c.user_id).where(
                    project_connections_table.c.project_id == str(project_id)
                )
            ).all()
        return tuple(UserId(row._mapping["user_id"]) for row in rows)


class SQLAlchemyAuthorizationRepository(AuthorizationRepository):
    """SQLAlchemy-backed authorization repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, authorization: Authorization) -> None:
        await self.save(authorization)

    async def get(self, authorization_id: AuthorizationId) -> Authorization:
        with self._database.engine.begin() as connection:
            request_row = connection.execute(
                select(authorization_requests_table).where(
                    authorization_requests_table.c.id == str(authorization_id)
                )
            ).first()
            decision_rows = connection.execute(
                select(authorization_decisions_table)
                .where(
                    authorization_decisions_table.c.request_id == str(authorization_id)
                )
                .order_by(authorization_decisions_table.c.decided_at)
            ).all()
        if request_row is None:
            raise LookupError(str(authorization_id))
        return _authorization_from_rows(
            request_row._mapping,
            [row._mapping for row in decision_rows],
        )

    async def save(self, authorization: Authorization) -> None:
        request_values = _authorization_request_to_values(authorization)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(authorization_requests_table.c.id).where(
                    authorization_requests_table.c.id == request_values["id"]
                )
            ).first()
            if exists is None:
                connection.execute(
                    insert(authorization_requests_table).values(**request_values)
                )
            else:
                connection.execute(
                    update(authorization_requests_table)
                    .where(authorization_requests_table.c.id == request_values["id"])
                    .values(**request_values)
                )

            connection.execute(
                delete(authorization_decisions_table).where(
                    authorization_decisions_table.c.request_id
                    == str(authorization.id)
                )
            )
            for decision in authorization.decisions:
                connection.execute(
                    insert(authorization_decisions_table).values(
                        **_authorization_decision_to_values(decision)
                    )
                )

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        status: AuthorizationDecisionStatus | None = None,
        pending_only: bool = False,
        limit: int = 20,
    ) -> tuple[Authorization, ...]:
        normalized_limit = _normalize_limit(limit)
        # A decision-based filter (status/pending_only) is only known after
        # decisions are joined in, so widen the candidate window before
        # filtering rather than truncating to `limit` before we can tell
        # which rows actually match.
        fetch_limit = (
            min(max(normalized_limit * 5, 100), 500)
            if (status is not None or pending_only)
            else normalized_limit
        )
        query = select(authorization_requests_table).order_by(
            authorization_requests_table.c.created_at.desc(),
            authorization_requests_table.c.id.desc(),
        )
        if task_id is not None:
            query = query.where(authorization_requests_table.c.task_id == str(task_id))
        query = query.limit(fetch_limit)
        with self._database.engine.begin() as connection:
            request_rows = connection.execute(query).all()
            if not request_rows:
                return ()
            request_ids = [row._mapping["id"] for row in request_rows]
            decision_rows = connection.execute(
                select(authorization_decisions_table)
                .where(authorization_decisions_table.c.request_id.in_(request_ids))
                .order_by(
                    authorization_decisions_table.c.request_id,
                    authorization_decisions_table.c.decided_at,
                    authorization_decisions_table.c.id,
                )
            ).all()

        decisions_by_request: dict[str, list[Mapping[str, Any]]] = {
            request_id: [] for request_id in request_ids
        }
        for row in decision_rows:
            mapping = row._mapping
            decisions_by_request[mapping["request_id"]].append(mapping)

        authorizations = (
            _authorization_from_rows(
                request_row._mapping,
                decisions_by_request[request_row._mapping["id"]],
            )
            for request_row in request_rows
        )
        if status is not None:
            authorizations = (a for a in authorizations if a.status is status)
        if pending_only:
            authorizations = (a for a in authorizations if a.status is None)
        return tuple(authorizations)[:normalized_limit]


class SQLAlchemyExecutionRepository(ExecutionRepository):
    """SQLAlchemy-backed execution repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, execution: Execution) -> None:
        await self.save(execution)

    async def get(self, execution_id: ExecutionId) -> Execution:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(executions_table).where(executions_table.c.id == str(execution_id))
            ).first()
        if row is None:
            raise LookupError(str(execution_id))
        return _execution_from_row(row._mapping)

    async def save(self, execution: Execution) -> None:
        values = _execution_to_values(execution)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(executions_table.c.id).where(executions_table.c.id == values["id"])
            ).first()
            if exists is None:
                connection.execute(insert(executions_table).values(**values))
            else:
                connection.execute(
                    update(executions_table)
                    .where(executions_table.c.id == values["id"])
                    .values(**values)
                )

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        state: ExecutionState | None = None,
        limit: int = 20,
    ) -> tuple[Execution, ...]:
        query = select(executions_table).order_by(
            executions_table.c.created_at.desc(),
            executions_table.c.id.desc(),
        )
        if task_id is not None:
            query = query.where(executions_table.c.task_id == str(task_id))
        if project_id is not None:
            query = query.where(executions_table.c.project_id == str(project_id))
        if state is not None:
            query = query.where(executions_table.c.state == state.value)
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_execution_from_row(row._mapping) for row in rows)


class SQLAlchemyEventRepository(EventRepository):
    """SQLAlchemy-backed durable domain event history."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, event: DomainEvent) -> None:
        values = _event_to_values(event)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(events_table.c.id).where(events_table.c.id == values["id"])
            ).first()
            if exists is None:
                connection.execute(insert(events_table).values(**values))

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        event_type: EventType | None = None,
        limit: int = 20,
    ) -> tuple[DomainEvent, ...]:
        query = select(events_table).order_by(
            events_table.c.occurred_at.desc(),
            events_table.c.id.desc(),
        )
        if task_id is not None:
            query = query.where(events_table.c.task_id == str(task_id))
        if project_id is not None:
            query = query.where(events_table.c.project_id == str(project_id))
        if execution_id is not None:
            query = query.where(events_table.c.execution_id == str(execution_id))
        if event_type is not None:
            query = query.where(events_table.c.event_type == event_type.value)
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_event_from_row(row._mapping) for row in rows)


class SQLAlchemyAuditRepository(AuditRepository):
    """SQLAlchemy-backed append-oriented audit history."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, record: AuditRecord) -> None:
        values = _audit_record_to_values(record)
        with self._database.engine.begin() as connection:
            if record.event_id is not None:
                existing_event_record = connection.execute(
                    select(audit_records_table.c.id).where(
                        audit_records_table.c.event_id == str(record.event_id)
                    )
                ).first()
                if existing_event_record is not None:
                    return

            exists = connection.execute(
                select(audit_records_table.c.id).where(
                    audit_records_table.c.id == values["id"]
                )
            ).first()
            if exists is None:
                connection.execute(insert(audit_records_table).values(**values))

    async def get(self, audit_id: AuditRecordId) -> AuditRecord:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(audit_records_table).where(
                    audit_records_table.c.id == str(audit_id)
                )
            ).first()
        if row is None:
            raise LookupError(str(audit_id))
        return _audit_record_from_row(row._mapping)

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        authorization_id: AuthorizationId | None = None,
        limit: int = 20,
    ) -> tuple[AuditRecord, ...]:
        query = select(audit_records_table).order_by(
            audit_records_table.c.occurred_at.desc(),
            audit_records_table.c.id.desc(),
        )
        if task_id is not None:
            query = query.where(audit_records_table.c.task_id == str(task_id))
        if project_id is not None:
            query = query.where(audit_records_table.c.project_id == str(project_id))
        if execution_id is not None:
            query = query.where(audit_records_table.c.execution_id == str(execution_id))
        if authorization_id is not None:
            query = query.where(
                audit_records_table.c.authorization_id == str(authorization_id)
            )
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_audit_record_from_row(row._mapping) for row in rows)


class SQLAlchemyContextResolutionRepository(ContextResolutionRepository):
    """SQLAlchemy-backed resolved context metadata repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add_many(self, records: tuple[ContextResolutionRecord, ...]) -> None:
        with self._database.engine.begin() as connection:
            for record in records:
                values = _context_resolution_record_to_values(record)
                exists = connection.execute(
                    select(context_resolution_records_table.c.id).where(
                        context_resolution_records_table.c.id == values["id"]
                    )
                ).first()
                if exists is None:
                    connection.execute(
                        insert(context_resolution_records_table).values(**values)
                    )

    async def list_by_execution(
        self,
        execution_id: ExecutionId,
    ) -> tuple[ContextResolutionRecord, ...]:
        query = (
            select(context_resolution_records_table)
            .where(context_resolution_records_table.c.execution_id == str(execution_id))
            .order_by(context_resolution_records_table.c.resolved_at)
        )
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_context_resolution_record_from_row(row._mapping) for row in rows)


class SQLAlchemyMetricsRepository(MetricsRepository):
    """SQLAlchemy-backed operational metrics repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add_many(self, records: tuple[MetricRecord, ...]) -> None:
        with self._database.engine.begin() as connection:
            for record in records:
                values = _metric_record_to_values(record)
                exists = connection.execute(
                    select(metric_records_table.c.id).where(
                        metric_records_table.c.id == values["id"]
                    )
                ).first()
                if exists is None:
                    connection.execute(insert(metric_records_table).values(**values))

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        name: str | None = None,
        limit: int = 20,
    ) -> tuple[MetricRecord, ...]:
        query = select(metric_records_table).order_by(
            metric_records_table.c.observed_at.desc(),
            metric_records_table.c.id.desc(),
        )
        if task_id is not None:
            query = query.where(metric_records_table.c.task_id == str(task_id))
        if project_id is not None:
            query = query.where(metric_records_table.c.project_id == str(project_id))
        if execution_id is not None:
            query = query.where(metric_records_table.c.execution_id == str(execution_id))
        if name is not None:
            query = query.where(metric_records_table.c.name == name)
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_metric_record_from_row(row._mapping) for row in rows)


class SQLAlchemySuggestionRepository(SuggestionRepository):
    """SQLAlchemy-backed suggestion repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, suggestion: Suggestion) -> None:
        await self.save(suggestion)

    async def save(self, suggestion: Suggestion) -> None:
        values = _suggestion_to_values(suggestion)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(suggestions_table.c.id).where(
                    suggestions_table.c.id == values["id"]
                )
            ).first()
            if exists is None:
                connection.execute(insert(suggestions_table).values(**values))
            else:
                connection.execute(
                    update(suggestions_table)
                    .where(suggestions_table.c.id == values["id"])
                    .values(**values)
                )

    async def get(self, suggestion_id: SuggestionId) -> Suggestion:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(suggestions_table).where(
                    suggestions_table.c.id == str(suggestion_id)
                )
            ).first()
        if row is None:
            raise LookupError(str(suggestion_id))
        return _suggestion_from_row(row._mapping)

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        limit: int = 20,
    ) -> tuple[Suggestion, ...]:
        query = select(suggestions_table).order_by(
            suggestions_table.c.generated_at.desc(),
            suggestions_table.c.id.desc(),
        )
        if task_id is not None:
            query = query.where(suggestions_table.c.task_id == str(task_id))
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_suggestion_from_row(row._mapping) for row in rows)


class SQLAlchemyUserRepository(IdentityUserRepository):
    """SQLAlchemy-backed user repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, user: User) -> None:
        await self.save(user)

    async def get(self, user_id: UserId) -> User:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(users_table).where(users_table.c.id == str(user_id))
            ).first()
        if row is None:
            raise LookupError(str(user_id))
        return _user_from_row(row._mapping)

    async def get_by_username(self, username: str) -> User | None:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(users_table).where(users_table.c.username == username.strip())
            ).first()
        return _user_from_row(row._mapping) if row is not None else None

    async def save(self, user: User) -> None:
        values = _user_to_values(user)
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(users_table.c.id).where(users_table.c.id == values["id"])
            ).first()
            if exists is None:
                connection.execute(insert(users_table).values(**values))
            else:
                connection.execute(
                    update(users_table)
                    .where(users_table.c.id == values["id"])
                    .values(**values)
                )

    async def list(
        self,
        *,
        is_active: bool | None = None,
        limit: int = 20,
    ) -> tuple[User, ...]:
        query = select(users_table).order_by(users_table.c.created_at.desc())
        if is_active is not None:
            query = query.where(users_table.c.is_active == int(is_active))
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_user_from_row(row._mapping) for row in rows)


class SQLAlchemyAccessRoleRepository(AccessRoleRepository):
    """SQLAlchemy-backed access-role repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, role: AccessRole) -> None:
        with self._database.engine.begin() as connection:
            connection.execute(insert(access_roles_table).values(**_access_role_to_values(role)))

    async def get(self, role_id: AccessRoleId) -> AccessRole:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(access_roles_table).where(access_roles_table.c.id == str(role_id))
            ).first()
        if row is None:
            raise LookupError(str(role_id))
        return _access_role_from_row(row._mapping)

    async def get_by_name(self, name: str) -> AccessRole | None:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(access_roles_table).where(
                    access_roles_table.c.name == name.strip()
                )
            ).first()
        return _access_role_from_row(row._mapping) if row is not None else None

    async def list(self, *, limit: int = 50) -> tuple[AccessRole, ...]:
        query = select(access_roles_table).order_by(access_roles_table.c.name.asc())
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_access_role_from_row(row._mapping) for row in rows)


class SQLAlchemyPermissionRepository(IdentityPermissionRepository):
    """SQLAlchemy-backed permission repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, permission: Permission) -> None:
        with self._database.engine.begin() as connection:
            connection.execute(
                insert(permissions_table).values(**_permission_to_values(permission))
            )

    async def get(self, permission_id: PermissionId) -> Permission:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(permissions_table).where(
                    permissions_table.c.id == str(permission_id)
                )
            ).first()
        if row is None:
            raise LookupError(str(permission_id))
        return _permission_from_row(row._mapping)

    async def get_by_key(self, key: str) -> Permission | None:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(permissions_table).where(permissions_table.c.key == key.strip())
            ).first()
        return _permission_from_row(row._mapping) if row is not None else None

    async def list(self, *, limit: int = 100) -> tuple[Permission, ...]:
        query = select(permissions_table).order_by(permissions_table.c.key.asc())
        query = query.limit(_normalize_limit(limit))
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        return tuple(_permission_from_row(row._mapping) for row in rows)

    def seed_catalog(self, catalog: Mapping[str, str]) -> None:
        """Idempotently ensure every key in `catalog` exists as a Permission row.

        Deliberately synchronous (unlike every other method on this class):
        called from `bootstrap.runtime.build_sqlalchemy_identity_runtime`
        right after `database.migrate()`, which is itself a plain sync
        function invoked from both async FastAPI startup and sync `orchai`
        CLI entry points. Bridging into the async port there (e.g. via
        `asyncio.run`) would raise under FastAPI's already-running event
        loop, so this uses the same raw, synchronous SQLAlchemy Core style
        as `SQLAlchemyDatabase.migrate()` instead of `self.add()`.

        Without this, `permissions`/`access_roles` start empty in a fresh
        database and no non-superuser can ever pass a permission check --
        see `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §4.
        """
        with self._database.engine.begin() as connection:
            existing_keys = {
                row._mapping["key"]
                for row in connection.execute(select(permissions_table.c.key)).all()
            }
            missing = {
                key: description
                for key, description in catalog.items()
                if key not in existing_keys
            }
            if not missing:
                return
            connection.execute(
                insert(permissions_table),
                [
                    _permission_to_values(Permission(key=key, description=description))
                    for key, description in missing.items()
                ],
            )


class SQLAlchemyRefreshTokenRepository(IdentityRefreshTokenRepository):
    """SQLAlchemy-backed refresh-token repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, token: RefreshToken) -> None:
        with self._database.engine.begin() as connection:
            connection.execute(
                insert(refresh_tokens_table).values(**_refresh_token_to_values(token))
            )

    async def get(self, token_id: RefreshTokenId) -> RefreshToken:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(refresh_tokens_table).where(
                    refresh_tokens_table.c.id == str(token_id)
                )
            ).first()
        if row is None:
            raise LookupError(str(token_id))
        return _refresh_token_from_row(row._mapping)

    async def save(self, token: RefreshToken) -> None:
        values = _refresh_token_to_values(token)
        with self._database.engine.begin() as connection:
            connection.execute(
                update(refresh_tokens_table)
                .where(refresh_tokens_table.c.id == values["id"])
                .values(**values)
            )

    async def list_for_user(
        self,
        user_id: UserId,
        *,
        active_only: bool = False,
    ) -> tuple[RefreshToken, ...]:
        query = select(refresh_tokens_table).where(
            refresh_tokens_table.c.user_id == str(user_id)
        )
        with self._database.engine.begin() as connection:
            rows = connection.execute(query).all()
        tokens = tuple(_refresh_token_from_row(row._mapping) for row in rows)
        if active_only:
            tokens = tuple(token for token in tokens if token.is_active())
        return tokens

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        with self._database.engine.begin() as connection:
            row = connection.execute(
                select(refresh_tokens_table).where(
                    refresh_tokens_table.c.token_hash == token_hash
                )
            ).first()
        if row is None:
            return None
        return _refresh_token_from_row(row._mapping)


class SQLAlchemyAccessControlRepository(AccessControlRepository):
    """SQLAlchemy-backed store for the identity many-to-many grants."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def assign_role(self, user_id: UserId, role_id: AccessRoleId) -> None:
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(user_roles_table.c.user_id).where(
                    user_roles_table.c.user_id == str(user_id),
                    user_roles_table.c.role_id == str(role_id),
                )
            ).first()
            if exists is None:
                connection.execute(
                    insert(user_roles_table).values(
                        user_id=str(user_id), role_id=str(role_id)
                    )
                )

    async def revoke_role(self, user_id: UserId, role_id: AccessRoleId) -> None:
        with self._database.engine.begin() as connection:
            connection.execute(
                delete(user_roles_table).where(
                    user_roles_table.c.user_id == str(user_id),
                    user_roles_table.c.role_id == str(role_id),
                )
            )

    async def grant_permission(self, user_id: UserId, permission_id: PermissionId) -> None:
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(user_permissions_table.c.user_id).where(
                    user_permissions_table.c.user_id == str(user_id),
                    user_permissions_table.c.permission_id == str(permission_id),
                )
            ).first()
            if exists is None:
                connection.execute(
                    insert(user_permissions_table).values(
                        user_id=str(user_id), permission_id=str(permission_id)
                    )
                )

    async def revoke_permission(
        self,
        user_id: UserId,
        permission_id: PermissionId,
    ) -> None:
        with self._database.engine.begin() as connection:
            connection.execute(
                delete(user_permissions_table).where(
                    user_permissions_table.c.user_id == str(user_id),
                    user_permissions_table.c.permission_id == str(permission_id),
                )
            )

    async def add_permission_to_role(
        self,
        role_id: AccessRoleId,
        permission_id: PermissionId,
    ) -> None:
        with self._database.engine.begin() as connection:
            exists = connection.execute(
                select(role_permissions_table.c.role_id).where(
                    role_permissions_table.c.role_id == str(role_id),
                    role_permissions_table.c.permission_id == str(permission_id),
                )
            ).first()
            if exists is None:
                connection.execute(
                    insert(role_permissions_table).values(
                        role_id=str(role_id), permission_id=str(permission_id)
                    )
                )

    async def remove_permission_from_role(
        self,
        role_id: AccessRoleId,
        permission_id: PermissionId,
    ) -> None:
        with self._database.engine.begin() as connection:
            connection.execute(
                delete(role_permissions_table).where(
                    role_permissions_table.c.role_id == str(role_id),
                    role_permissions_table.c.permission_id == str(permission_id),
                )
            )

    async def list_role_ids_for_user(self, user_id: UserId) -> tuple[AccessRoleId, ...]:
        with self._database.engine.begin() as connection:
            rows = connection.execute(
                select(user_roles_table.c.role_id).where(
                    user_roles_table.c.user_id == str(user_id)
                )
            ).all()
        return tuple(AccessRoleId(row._mapping["role_id"]) for row in rows)

    async def list_user_ids_for_role(self, role_id: AccessRoleId) -> tuple[UserId, ...]:
        with self._database.engine.begin() as connection:
            rows = connection.execute(
                select(user_roles_table.c.user_id).where(
                    user_roles_table.c.role_id == str(role_id)
                )
            ).all()
        return tuple(UserId(row._mapping["user_id"]) for row in rows)

    async def list_direct_permission_ids_for_user(
        self,
        user_id: UserId,
    ) -> tuple[PermissionId, ...]:
        with self._database.engine.begin() as connection:
            rows = connection.execute(
                select(user_permissions_table.c.permission_id).where(
                    user_permissions_table.c.user_id == str(user_id)
                )
            ).all()
        return tuple(PermissionId(row._mapping["permission_id"]) for row in rows)

    async def list_permission_ids_for_role(
        self,
        role_id: AccessRoleId,
    ) -> tuple[PermissionId, ...]:
        with self._database.engine.begin() as connection:
            rows = connection.execute(
                select(role_permissions_table.c.permission_id).where(
                    role_permissions_table.c.role_id == str(role_id)
                )
            ).all()
        return tuple(PermissionId(row._mapping["permission_id"]) for row in rows)


def _task_to_values(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "project_id": str(task.project_id) if task.project_id is not None else None,
        "execution_mode": task.execution_mode.value,
        "state": task.state.value,
        "requested_change": task.scope.requested_change,
        "acceptance_criteria": _to_json(task.scope.acceptance_criteria),
        "constraints": _to_json(task.scope.constraints),
        "exclusions": _to_json(task.scope.exclusions),
    }


def _project_to_values(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "root_location": project.root_location,
        "adapter_type": project.adapter_type,
        "capabilities": _to_json(
            [capability.value for capability in project.capabilities]
        ),
        "status": project.status.value,
        "readiness_level": project.readiness_level.value,
        "security_profile": _to_json(project.security_profile.as_dict()),
        "observed_readiness_level": project.observed_readiness_level.value,
        "observed_security_profile": _to_json(
            project.observed_security_profile.as_dict()
        ),
    }


def _authorization_request_to_values(authorization: Authorization) -> dict[str, Any]:
    request = authorization.request
    operation = request.operation
    return {
        "id": str(request.id),
        "task_id": str(request.task_id),
        "role": operation.role.value,
        "action": operation.action.value,
        "model_id": str(operation.model_id) if operation.model_id is not None else None,
        "context_scope": _to_json(operation.context_scope),
        "proposed_state": operation.proposed_state.value
        if operation.proposed_state is not None
        else None,
        "reason": request.reason,
        "requester": request.requester,
        "execution_mode": request.execution_mode.value,
        "created_at": request.created_at.isoformat(),
        "expires_at": request.expires_at.isoformat()
        if request.expires_at is not None
        else None,
    }


def _authorization_decision_to_values(
    decision: AuthorizationDecision,
) -> dict[str, Any]:
    return {
        "id": str(decision.id),
        "request_id": str(decision.request_id),
        "status": decision.status.value,
        "decided_by": decision.decided_by,
        "reason": decision.reason,
        "decided_at": decision.decided_at.isoformat(),
    }


def _execution_to_values(execution: Execution) -> dict[str, Any]:
    result = execution.result
    return {
        "id": str(execution.id),
        "task_id": str(execution.task_id),
        "role": execution.role.value,
        "action": execution.action.value,
        "model_id": str(execution.model_id),
        "authorization_id": str(execution.authorization_id),
        "project_id": str(execution.project_id) if execution.project_id else None,
        "requested_context": _to_json(execution.requested_context),
        "authorized_context": _to_json(execution.authorized_context),
        "created_at": execution.created_at.isoformat(),
        "started_at": execution.started_at.isoformat()
        if execution.started_at is not None
        else None,
        "completed_at": execution.completed_at.isoformat()
        if execution.completed_at is not None
        else None,
        "state": execution.state.value,
        "result_output": result.output if result is not None else None,
        "result_success": int(result.success) if result is not None else None,
        "result_errors": _to_json(result.errors) if result is not None else None,
        "result_warnings": _to_json(result.warnings) if result is not None else None,
        "result_resource_usage": _to_json(
            _resource_usage_to_dict(result.resource_usage)
        )
        if result is not None
        else None,
        "result_metadata": _to_json(result.metadata) if result is not None else None,
    }


def _event_to_values(event: DomainEvent) -> dict[str, Any]:
    return {
        "id": str(event.event_id),
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "source": event.source,
        "task_id": str(event.task_id) if event.task_id is not None else None,
        "project_id": str(event.project_id) if event.project_id is not None else None,
        "execution_id": str(event.execution_id)
        if event.execution_id is not None
        else None,
        "correlation_id": str(event.correlation_id)
        if event.correlation_id is not None
        else None,
        "causation_id": str(event.causation_id)
        if event.causation_id is not None
        else None,
        "payload": _to_json(event.payload),
    }


def _audit_record_to_values(record: AuditRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "occurred_at": record.occurred_at.isoformat(),
        "actor": record.actor,
        "operation": record.operation,
        "outcome": record.outcome,
        "task_id": str(record.task_id) if record.task_id is not None else None,
        "project_id": str(record.project_id) if record.project_id is not None else None,
        "execution_id": str(record.execution_id)
        if record.execution_id is not None
        else None,
        "authorization_id": str(record.authorization_id)
        if record.authorization_id is not None
        else None,
        "event_id": str(record.event_id) if record.event_id is not None else None,
        "correlation_id": str(record.correlation_id)
        if record.correlation_id is not None
        else None,
        "causation_id": str(record.causation_id)
        if record.causation_id is not None
        else None,
        "metadata": _to_json(record.metadata),
    }


def _context_resolution_record_to_values(
    record: ContextResolutionRecord,
) -> dict[str, Any]:
    reference = record.reference
    return {
        "id": str(record.id),
        "execution_id": str(record.execution_id),
        "project_id": str(record.project_id),
        "source": reference.source.value,
        "resource": reference.resource,
        "scope": reference.scope,
        "version": reference.version,
        "content_sha256": record.content_sha256,
        "content_bytes": record.content_bytes,
        "resolved_at": record.resolved_at.isoformat(),
        "metadata": _to_json(record.metadata),
    }


def _metric_record_to_values(record: MetricRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "observed_at": record.observed_at.isoformat(),
        "name": record.name,
        "value": record.value,
        "unit": record.unit,
        "task_id": str(record.task_id) if record.task_id is not None else None,
        "project_id": str(record.project_id) if record.project_id is not None else None,
        "execution_id": str(record.execution_id)
        if record.execution_id is not None
        else None,
        "dimensions": _to_json(record.dimensions),
    }


def _suggestion_to_values(suggestion: Suggestion) -> dict[str, Any]:
    return {
        "id": str(suggestion.id),
        "task_id": str(suggestion.task_id),
        "related_execution_id": str(suggestion.related_execution_id)
        if suggestion.related_execution_id is not None
        else None,
        "suggested_role": suggestion.suggested_role.value,
        "suggested_action": suggestion.suggested_action.value,
        "rationale": suggestion.rationale,
        "required_capabilities": _to_json(
            [capability.value for capability in suggestion.required_capabilities]
        ),
        "expected_impact": suggestion.expected_impact,
        "authorization_required": int(suggestion.authorization_required),
        "confidence": suggestion.confidence,
        "status": suggestion.status.value,
        "generated_at": suggestion.generated_at.isoformat(),
        "metadata": _to_json(suggestion.metadata),
    }


def _user_to_values(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "password_hash": user.password_hash,
        "is_superuser": int(user.is_superuser),
        "is_active": int(user.is_active),
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


def _access_role_to_values(role: AccessRole) -> dict[str, Any]:
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
    }


def _permission_to_values(permission: Permission) -> dict[str, Any]:
    return {
        "id": str(permission.id),
        "key": permission.key,
        "description": permission.description,
    }


def _refresh_token_to_values(token: RefreshToken) -> dict[str, Any]:
    return {
        "id": str(token.id),
        "user_id": str(token.user_id),
        "token_hash": token.token_hash,
        "issued_at": token.issued_at.isoformat(),
        "expires_at": token.expires_at.isoformat(),
        "revoked_at": token.revoked_at.isoformat() if token.revoked_at is not None else None,
    }


def _user_from_row(row: Mapping[str, Any]) -> User:
    return User(
        id=UserId(row["id"]),
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_superuser=bool(row["is_superuser"]),
        is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _access_role_from_row(row: Mapping[str, Any]) -> AccessRole:
    return AccessRole(
        id=AccessRoleId(row["id"]),
        name=row["name"],
        description=row["description"],
    )


def _permission_from_row(row: Mapping[str, Any]) -> Permission:
    return Permission(
        id=PermissionId(row["id"]),
        key=row["key"],
        description=row["description"],
    )


def _refresh_token_from_row(row: Mapping[str, Any]) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId(row["id"]),
        user_id=UserId(row["user_id"]),
        token_hash=row["token_hash"],
        issued_at=datetime.fromisoformat(row["issued_at"]),
        expires_at=datetime.fromisoformat(row["expires_at"]),
        revoked_at=datetime.fromisoformat(row["revoked_at"])
        if row["revoked_at"] is not None
        else None,
    )


def _task_from_row(row: Mapping[str, Any]) -> Task:
    task = Task(
        id=TaskId(row["id"]),
        title=row["title"],
        description=row["description"],
        project_id=ProjectId(row["project_id"]) if row["project_id"] else None,
        execution_mode=ExecutionMode(row["execution_mode"]),
        scope=TaskScope(
            requested_change=row["requested_change"],
            acceptance_criteria=tuple(_from_json(row["acceptance_criteria"])),
            constraints=tuple(_from_json(row["constraints"])),
            exclusions=tuple(_from_json(row["exclusions"])),
        ),
    )
    task._state = TaskState(row["state"])
    return task


def _project_from_row(row: Mapping[str, Any]) -> Project:
    return Project(
        id=ProjectId(row["id"]),
        name=row["name"],
        root_location=row["root_location"],
        adapter_type=row["adapter_type"],
        capabilities=frozenset(
            CapabilityName(value) for value in _from_json(row["capabilities"])
        ),
        status=ProjectStatus(row["status"]),
        readiness_level=ProjectReadinessLevel(
            row.get("readiness_level") or ProjectReadinessLevel.LEVEL_0_CONNECTABLE
        ),
        security_profile=ProjectSecurityProfile.from_dict(
            _from_json(row.get("security_profile") or "{}")
        ),
        observed_readiness_level=ProjectReadinessLevel(
            row.get("observed_readiness_level")
            or row.get("readiness_level")
            or ProjectReadinessLevel.LEVEL_0_CONNECTABLE
        ),
        observed_security_profile=ProjectSecurityProfile.from_dict(
            _from_json(
                row.get("observed_security_profile")
                or row.get("security_profile")
                or "{}"
            )
        ),
    )


def _authorization_from_rows(
    request_row: Mapping[str, Any],
    decision_rows: list[Mapping[str, Any]],
) -> Authorization:
    operation = RequestedOperation(
        role=RoleName(request_row["role"]),
        action=ActionName(request_row["action"]),
        model_id=ModelId(request_row["model_id"])
        if request_row["model_id"] is not None
        else None,
        context_scope=tuple(_from_json(request_row["context_scope"])),
        proposed_state=TaskState(request_row["proposed_state"])
        if request_row["proposed_state"] is not None
        else None,
    )
    request = AuthorizationRequest(
        id=AuthorizationId(request_row["id"]),
        task_id=TaskId(request_row["task_id"]),
        operation=operation,
        reason=request_row["reason"],
        requester=request_row["requester"],
        execution_mode=ExecutionMode(request_row["execution_mode"]),
        created_at=datetime.fromisoformat(request_row["created_at"]),
        expires_at=datetime.fromisoformat(request_row["expires_at"])
        if request_row["expires_at"] is not None
        else None,
    )
    decisions = tuple(
        AuthorizationDecision(
            id=AuthorizationDecisionId(row["id"]),
            request_id=AuthorizationId(row["request_id"]),
            status=AuthorizationDecisionStatus(row["status"]),
            decided_by=row["decided_by"],
            reason=row["reason"],
            decided_at=datetime.fromisoformat(row["decided_at"]),
        )
        for row in decision_rows
    )
    return Authorization(request=request, decisions=decisions)


def _execution_from_row(row: Mapping[str, Any]) -> Execution:
    execution = Execution(
        id=ExecutionId(row["id"]),
        task_id=TaskId(row["task_id"]),
        role=RoleName(row["role"]),
        action=ActionName(row["action"]),
        model_id=ModelId(row["model_id"]),
        authorization_id=AuthorizationId(row["authorization_id"]),
        project_id=ProjectId(row["project_id"]) if row["project_id"] else None,
        requested_context=tuple(_from_json(row["requested_context"])),
        authorized_context=tuple(_from_json(row["authorized_context"])),
        created_at=datetime.fromisoformat(row["created_at"]),
        started_at=datetime.fromisoformat(row["started_at"])
        if row["started_at"] is not None
        else None,
        completed_at=datetime.fromisoformat(row["completed_at"])
        if row["completed_at"] is not None
        else None,
    )
    execution._state = ExecutionState(row["state"])
    if row["result_success"] is not None:
        usage = _resource_usage_from_dict(_from_json(row["result_resource_usage"]))
        execution.result = ExecutionResult(
            output=row["result_output"] or "",
            success=bool(row["result_success"]),
            errors=tuple(_from_json(row["result_errors"])),
            warnings=tuple(_from_json(row["result_warnings"])),
            resource_usage=usage,
            metadata=_from_json(row["result_metadata"]),
        )
    return execution


def _event_from_row(row: Mapping[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_id=EventId(row["id"]),
        event_type=EventType(row["event_type"]),
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        source=row["source"],
        task_id=TaskId(row["task_id"]) if row["task_id"] else None,
        project_id=ProjectId(row["project_id"]) if row["project_id"] else None,
        execution_id=ExecutionId(row["execution_id"]) if row["execution_id"] else None,
        correlation_id=CorrelationId(row["correlation_id"])
        if row["correlation_id"]
        else None,
        causation_id=CausationId(row["causation_id"]) if row["causation_id"] else None,
        payload=_from_json(row["payload"]),
    )


def _audit_record_from_row(row: Mapping[str, Any]) -> AuditRecord:
    return AuditRecord(
        id=AuditRecordId(row["id"]),
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        actor=row["actor"],
        operation=row["operation"],
        outcome=row["outcome"],
        task_id=TaskId(row["task_id"]) if row["task_id"] else None,
        project_id=ProjectId(row["project_id"]) if row["project_id"] else None,
        execution_id=ExecutionId(row["execution_id"]) if row["execution_id"] else None,
        authorization_id=AuthorizationId(row["authorization_id"])
        if row["authorization_id"]
        else None,
        event_id=EventId(row["event_id"]) if row["event_id"] else None,
        correlation_id=CorrelationId(row["correlation_id"])
        if row["correlation_id"]
        else None,
        causation_id=CausationId(row["causation_id"]) if row["causation_id"] else None,
        metadata=_from_json(row["metadata"]),
    )


def _context_resolution_record_from_row(
    row: Mapping[str, Any],
) -> ContextResolutionRecord:
    return ContextResolutionRecord(
        id=ContextResolutionId(row["id"]),
        execution_id=ExecutionId(row["execution_id"]),
        project_id=ProjectId(row["project_id"]),
        reference=ContextReference(
            source=ContextSource(row["source"]),
            resource=row["resource"],
            scope=row["scope"],
            version=row["version"],
        ),
        content_sha256=row["content_sha256"],
        content_bytes=row["content_bytes"],
        resolved_at=datetime.fromisoformat(row["resolved_at"]),
        metadata=_from_json(row["metadata"]),
    )


def _metric_record_from_row(row: Mapping[str, Any]) -> MetricRecord:
    return MetricRecord(
        id=MetricRecordId(row["id"]),
        observed_at=datetime.fromisoformat(row["observed_at"]),
        name=row["name"],
        value=row["value"],
        unit=row["unit"],
        task_id=TaskId(row["task_id"]) if row["task_id"] else None,
        project_id=ProjectId(row["project_id"]) if row["project_id"] else None,
        execution_id=ExecutionId(row["execution_id"]) if row["execution_id"] else None,
        dimensions=_from_json(row["dimensions"]),
    )


def _suggestion_from_row(row: Mapping[str, Any]) -> Suggestion:
    return Suggestion(
        id=SuggestionId(row["id"]),
        task_id=TaskId(row["task_id"]),
        related_execution_id=ExecutionId(row["related_execution_id"])
        if row["related_execution_id"]
        else None,
        suggested_role=RoleName(row["suggested_role"]),
        suggested_action=ActionName(row["suggested_action"]),
        rationale=row["rationale"],
        required_capabilities=frozenset(
            CapabilityName(value) for value in _from_json(row["required_capabilities"])
        ),
        expected_impact=row["expected_impact"],
        authorization_required=bool(row["authorization_required"]),
        confidence=row["confidence"],
        status=SuggestionStatus(row["status"]),
        generated_at=datetime.fromisoformat(row["generated_at"]),
        metadata=_from_json(row["metadata"]),
    )


def _resource_usage_to_dict(resource_usage: ResourceUsage) -> dict[str, Any]:
    return {
        "input_tokens": resource_usage.input_tokens,
        "output_tokens": resource_usage.output_tokens,
        "estimated_cost": resource_usage.estimated_cost,
        "metadata": dict(resource_usage.metadata),
    }


def _resource_usage_from_dict(data: dict[str, Any]) -> ResourceUsage:
    return ResourceUsage(
        input_tokens=data.get("input_tokens"),
        output_tokens=data.get("output_tokens"),
        estimated_cost=data.get("estimated_cost"),
        metadata=data.get("metadata", {}),
    )


def _to_json(value: Any) -> str:
    if isinstance(value, Mapping):
        value = dict(value)
    return json.dumps(value, sort_keys=True)


def _from_json(value: str | None) -> Any:
    if value is None:
        return []
    return json.loads(value)


def _normalize_limit(limit: int) -> int:
    if limit < 1:
        return 1
    return min(limit, 100)
