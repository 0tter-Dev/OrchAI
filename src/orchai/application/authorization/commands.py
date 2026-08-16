"""Authorization use-case commands."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.identifiers import AuthorizationId, ModelId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState


@dataclass(frozen=True, slots=True)
class RequestAuthorizationCommand:
    """Command for requesting authorization for a protected operation."""

    task_id: TaskId
    role: RoleName
    action: ActionName
    reason: str
    requester: str
    execution_mode: ExecutionMode
    model_id: ModelId | None = None
    context_scope: Iterable[str] = ()
    proposed_state: TaskState | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DecideAuthorizationCommand:
    """Command for recording an authorization decision."""

    authorization_id: AuthorizationId
    status: AuthorizationDecisionStatus
    decided_by: str
    reason: str

