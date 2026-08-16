"""SQLAlchemy repository implementations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.executions.ports import ExecutionRepository
from orchai.application.projects.ports import ProjectRepository
from orchai.application.tasks.ports import TaskRepository
from orchai.domain.actions import ActionName
from orchai.domain.authorization import (
    Authorization,
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationRequest,
    RequestedOperation,
)
from orchai.domain.capabilities import CapabilityName
from orchai.domain.executions import (
    Execution,
    ExecutionResult,
    ExecutionState,
    ResourceUsage,
)
from orchai.domain.identifiers import (
    AuthorizationDecisionId,
    AuthorizationId,
    ExecutionId,
    ModelId,
    ProjectId,
    TaskId,
)
from orchai.domain.projects import Project, ProjectStatus
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, Task, TaskScope, TaskState
from orchai.infrastructure.persistence.sqlalchemy.database import SQLAlchemyDatabase
from orchai.infrastructure.persistence.sqlalchemy.tables import (
    authorization_decisions_table,
    authorization_requests_table,
    executions_table,
    projects_table,
    tasks_table,
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


class SQLAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy-backed project repository."""

    def __init__(self, database: SQLAlchemyDatabase) -> None:
        self._database = database

    async def add(self, project: Project) -> None:
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

