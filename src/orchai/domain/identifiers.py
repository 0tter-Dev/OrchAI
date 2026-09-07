"""Stable domain identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Identifier:
    """Stable identity value shared by domain entities."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("identifier value must not be empty")
        object.__setattr__(self, "value", normalized)

    @classmethod
    def new(cls) -> Identifier:
        return cls(str(uuid4()))

    def __str__(self) -> str:
        return self.value


class TaskId(Identifier):
    """Stable task identity."""


class ProjectId(Identifier):
    """Stable external project identity."""


class ExecutionId(Identifier):
    """Stable execution identity."""


class AuthorizationId(Identifier):
    """Stable authorization identity."""


class AuthorizationDecisionId(Identifier):
    """Stable authorization decision identity."""


class RoleId(Identifier):
    """Stable role identity."""


class ActionId(Identifier):
    """Stable action identity."""


class ModelId(Identifier):
    """Stable model identity."""


class EventId(Identifier):
    """Stable event identity."""


class AuditRecordId(Identifier):
    """Stable audit record identity."""


class ContextResolutionId(Identifier):
    """Stable resolved context metadata identity."""


class MetricRecordId(Identifier):
    """Stable metric record identity."""


class SuggestionId(Identifier):
    """Stable suggestion identity."""


class CorrelationId(Identifier):
    """Stable correlation identity."""


class CausationId(Identifier):
    """Stable causation identity."""


class UserId(Identifier):
    """Stable identity-and-access-management user identity."""


class AccessRoleId(Identifier):
    """Stable access-role identity (identity/authorization grouping).

    Distinct from the reserved, unused `RoleId` above: `RoleId` was set
    aside for a *task* role identity mirroring `RoleName`
    (`domain.roles`), while `AccessRoleId` names a *permission-bundle*
    role in the identity/access-management layer (ADR-012). The two are
    intentionally kept separate to avoid a second, incompatible meaning
    for "role" in the codebase.
    """


class PermissionId(Identifier):
    """Stable identity-and-access-management permission identity."""


class RefreshTokenId(Identifier):
    """Stable refresh token identity."""


class ModuleId(Identifier):
    """Stable Module identity (ADR-015).

    Unlike most identifiers here, values are stable slugs (e.g. "forge"),
    not generated UUIDs -- `ModuleDefinition`s are a fixed, code-defined
    vocabulary (`application/modules/registry.py`), the same treatment
    already given to `RoleName`/`ActionName`.
    """


class ConversationId(Identifier):
    """Stable conversation identity (ADR-014)."""


class MessageId(Identifier):
    """Stable message identity (ADR-014)."""
