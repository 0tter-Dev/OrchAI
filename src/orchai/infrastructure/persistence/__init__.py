"""Persistence infrastructure."""

from orchai.infrastructure.persistence.in_memory_audit import InMemoryAuditRepository
from orchai.infrastructure.persistence.in_memory_authorizations import (
    InMemoryAuthorizationRepository,
)
from orchai.infrastructure.persistence.in_memory_context import (
    InMemoryContextResolutionRepository,
)
from orchai.infrastructure.persistence.in_memory_conversations import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
from orchai.infrastructure.persistence.in_memory_events import InMemoryEventRepository
from orchai.infrastructure.persistence.in_memory_executions import (
    InMemoryExecutionRepository,
)
from orchai.infrastructure.persistence.in_memory_identity import (
    InMemoryAccessControlRepository,
    InMemoryAccessRoleRepository,
    InMemoryPermissionRepository,
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)
from orchai.infrastructure.persistence.in_memory_metrics import InMemoryMetricsRepository
from orchai.infrastructure.persistence.in_memory_policies import (
    InMemoryAutomaticPolicyRepository,
)
from orchai.infrastructure.persistence.in_memory_projects import (
    InMemoryProjectConnectionRepository,
    InMemoryProjectRepository,
)
from orchai.infrastructure.persistence.in_memory_suggestions import (
    InMemorySuggestionRepository,
)
from orchai.infrastructure.persistence.in_memory_tasks import InMemoryTaskRepository
from orchai.infrastructure.persistence.sqlalchemy import (
    SQLAlchemyAccessControlRepository,
    SQLAlchemyAccessRoleRepository,
    SQLAlchemyAuditRepository,
    SQLAlchemyAuthorizationRepository,
    SQLAlchemyAutomaticPolicyRepository,
    SQLAlchemyContextResolutionRepository,
    SQLAlchemyConversationRepository,
    SQLAlchemyDatabase,
    SQLAlchemyEventRepository,
    SQLAlchemyExecutionRepository,
    SQLAlchemyMessageRepository,
    SQLAlchemyMetricsRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyProjectConnectionRepository,
    SQLAlchemyProjectRepository,
    SQLAlchemyRefreshTokenRepository,
    SQLAlchemySuggestionRepository,
    SQLAlchemyTaskRepository,
    SQLAlchemyUserRepository,
)

__all__ = [
    "InMemoryAccessControlRepository",
    "InMemoryAccessRoleRepository",
    "InMemoryAuditRepository",
    "InMemoryAuthorizationRepository",
    "InMemoryAutomaticPolicyRepository",
    "InMemoryContextResolutionRepository",
    "InMemoryConversationRepository",
    "InMemoryEventRepository",
    "InMemoryExecutionRepository",
    "InMemoryMessageRepository",
    "InMemoryMetricsRepository",
    "InMemoryPermissionRepository",
    "InMemoryProjectConnectionRepository",
    "InMemoryProjectRepository",
    "InMemoryRefreshTokenRepository",
    "InMemorySuggestionRepository",
    "InMemoryTaskRepository",
    "InMemoryUserRepository",
    "SQLAlchemyAccessControlRepository",
    "SQLAlchemyAccessRoleRepository",
    "SQLAlchemyAuditRepository",
    "SQLAlchemyAuthorizationRepository",
    "SQLAlchemyAutomaticPolicyRepository",
    "SQLAlchemyContextResolutionRepository",
    "SQLAlchemyConversationRepository",
    "SQLAlchemyDatabase",
    "SQLAlchemyEventRepository",
    "SQLAlchemyExecutionRepository",
    "SQLAlchemyMessageRepository",
    "SQLAlchemyMetricsRepository",
    "SQLAlchemyPermissionRepository",
    "SQLAlchemyProjectConnectionRepository",
    "SQLAlchemyProjectRepository",
    "SQLAlchemyRefreshTokenRepository",
    "SQLAlchemySuggestionRepository",
    "SQLAlchemyTaskRepository",
    "SQLAlchemyUserRepository",
]
