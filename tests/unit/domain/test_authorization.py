from datetime import UTC, datetime, timedelta

import pytest

from orchai.domain.actions import ActionName
from orchai.domain.authorization import (
    Authorization,
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationNotGrantedError,
    AuthorizationRequest,
    RequestedOperation,
)
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode


def test_granted_authorization_validates_exact_operation() -> None:
    operation = RequestedOperation(
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("codex"),
        context_scope=("src",),
    )
    authorization = Authorization.request_authorization(
        AuthorizationRequest(
            task_id=TaskId.new(),
            operation=operation,
            reason="Implement requested change.",
            requester="user",
            execution_mode=ExecutionMode.SUGGESTED,
        )
    )

    authorization.record_decision(
        AuthorizationDecision(
            request_id=authorization.id,
            status=AuthorizationDecisionStatus.GRANTED,
            decided_by="user",
            reason="Approved for this execution.",
        )
    )

    authorization.ensure_grants(operation=operation)


def test_rejected_authorization_does_not_grant_execution() -> None:
    operation = RequestedOperation(
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("codex"),
    )
    authorization = Authorization.request_authorization(
        AuthorizationRequest(
            task_id=TaskId.new(),
            operation=operation,
            reason="Implement requested change.",
            requester="user",
            execution_mode=ExecutionMode.SUGGESTED,
        )
    )
    authorization.record_decision(
        AuthorizationDecision(
            request_id=authorization.id,
            status=AuthorizationDecisionStatus.REJECTED,
            decided_by="user",
            reason="Not approved.",
        )
    )

    with pytest.raises(AuthorizationNotGrantedError):
        authorization.ensure_grants(operation=operation)


def test_expired_authorization_cannot_be_reused() -> None:
    created_at = datetime(2026, 8, 15, tzinfo=UTC)
    operation = RequestedOperation(
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("codex"),
    )
    authorization = Authorization.request_authorization(
        AuthorizationRequest(
            task_id=TaskId.new(),
            operation=operation,
            reason="Implement requested change.",
            requester="user",
            execution_mode=ExecutionMode.SUGGESTED,
            created_at=created_at,
            expires_at=created_at + timedelta(minutes=5),
        )
    )
    authorization.record_decision(
        AuthorizationDecision(
            request_id=authorization.id,
            status=AuthorizationDecisionStatus.GRANTED,
            decided_by="user",
            reason="Approved briefly.",
        )
    )

    with pytest.raises(AuthorizationNotGrantedError):
        authorization.ensure_grants(
            operation=operation,
            at=created_at + timedelta(minutes=6),
        )


def test_revoked_authorization_cannot_be_reused() -> None:
    operation = RequestedOperation(
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("codex"),
    )
    authorization = Authorization.request_authorization(
        AuthorizationRequest(
            task_id=TaskId.new(),
            operation=operation,
            reason="Implement requested change.",
            requester="user",
            execution_mode=ExecutionMode.SUGGESTED,
        )
    )
    authorization.record_decision(
        AuthorizationDecision(
            request_id=authorization.id,
            status=AuthorizationDecisionStatus.GRANTED,
            decided_by="user",
            reason="Approved.",
        )
    )
    authorization.record_decision(
        AuthorizationDecision(
            request_id=authorization.id,
            status=AuthorizationDecisionStatus.REVOKED,
            decided_by="user",
            reason="Revoked before execution.",
        )
    )

    with pytest.raises(AuthorizationNotGrantedError):
        authorization.ensure_grants(operation=operation)
