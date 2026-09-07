"""SQLAlchemy table definitions for OrchAI persistence."""

from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, MetaData, Table, Text

metadata = MetaData()

projects_table = Table(
    "projects",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("root_location", Text, nullable=False),
    Column("adapter_type", Text, nullable=False),
    Column("capabilities", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("readiness_level", Text, nullable=False),
    Column("security_profile", Text, nullable=False),
    Column("observed_readiness_level", Text, nullable=False),
    Column("observed_security_profile", Text, nullable=False),
)

tasks_table = Table(
    "tasks",
    metadata,
    Column("id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("project_id", Text, ForeignKey("projects.id")),
    Column("execution_mode", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("requested_change", Text, nullable=False),
    Column("acceptance_criteria", Text, nullable=False),
    Column("constraints", Text, nullable=False),
    Column("exclusions", Text, nullable=False),
)

authorization_requests_table = Table(
    "authorization_requests",
    metadata,
    Column("id", Text, primary_key=True),
    Column("task_id", Text, ForeignKey("tasks.id"), nullable=False),
    Column("role", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("model_id", Text),
    Column("context_scope", Text, nullable=False),
    Column("proposed_state", Text),
    Column("reason", Text, nullable=False),
    Column("requester", Text, nullable=False),
    Column("execution_mode", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("expires_at", Text),
)

authorization_decisions_table = Table(
    "authorization_decisions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("request_id", Text, ForeignKey("authorization_requests.id"), nullable=False),
    Column("status", Text, nullable=False),
    Column("decided_by", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("decided_at", Text, nullable=False),
)

executions_table = Table(
    "executions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("task_id", Text, ForeignKey("tasks.id"), nullable=False),
    Column("role", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("model_id", Text, nullable=False),
    Column("authorization_id", Text, ForeignKey("authorization_requests.id"), nullable=False),
    Column("project_id", Text, ForeignKey("projects.id")),
    Column("requested_context", Text, nullable=False),
    Column("authorized_context", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("started_at", Text),
    Column("completed_at", Text),
    Column("state", Text, nullable=False),
    Column("result_output", Text),
    Column("result_success", Integer),
    Column("result_errors", Text),
    Column("result_warnings", Text),
    Column("result_resource_usage", Text),
    Column("result_metadata", Text),
)

events_table = Table(
    "events",
    metadata,
    Column("id", Text, primary_key=True),
    Column("event_type", Text, nullable=False),
    Column("occurred_at", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("task_id", Text, ForeignKey("tasks.id")),
    Column("project_id", Text, ForeignKey("projects.id")),
    Column("execution_id", Text, ForeignKey("executions.id")),
    Column("correlation_id", Text),
    Column("causation_id", Text),
    Column("payload", Text, nullable=False),
)

audit_records_table = Table(
    "audit_records",
    metadata,
    Column("id", Text, primary_key=True),
    Column("occurred_at", Text, nullable=False),
    Column("actor", Text, nullable=False),
    Column("operation", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("task_id", Text, ForeignKey("tasks.id")),
    Column("project_id", Text, ForeignKey("projects.id")),
    Column("execution_id", Text, ForeignKey("executions.id")),
    Column("authorization_id", Text, ForeignKey("authorization_requests.id")),
    Column("event_id", Text, ForeignKey("events.id"), unique=True),
    Column("correlation_id", Text),
    Column("causation_id", Text),
    Column("metadata", Text, nullable=False),
)

context_resolution_records_table = Table(
    "context_resolution_records",
    metadata,
    Column("id", Text, primary_key=True),
    Column("execution_id", Text, ForeignKey("executions.id"), nullable=False),
    Column("project_id", Text, ForeignKey("projects.id"), nullable=False),
    Column("source", Text, nullable=False),
    Column("resource", Text, nullable=False),
    Column("scope", Text),
    Column("version", Text),
    Column("content_sha256", Text, nullable=False),
    Column("content_bytes", Integer, nullable=False),
    Column("resolved_at", Text, nullable=False),
    Column("metadata", Text, nullable=False),
)

metric_records_table = Table(
    "metric_records",
    metadata,
    Column("id", Text, primary_key=True),
    Column("observed_at", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("value", Float, nullable=False),
    Column("unit", Text, nullable=False),
    Column("task_id", Text, ForeignKey("tasks.id")),
    Column("project_id", Text, ForeignKey("projects.id")),
    Column("execution_id", Text, ForeignKey("executions.id")),
    Column("dimensions", Text, nullable=False),
)

suggestions_table = Table(
    "suggestions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("task_id", Text, ForeignKey("tasks.id"), nullable=False),
    Column("related_execution_id", Text, ForeignKey("executions.id")),
    Column("suggested_role", Text, nullable=False),
    Column("suggested_action", Text, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("required_capabilities", Text, nullable=False),
    Column("expected_impact", Text, nullable=False),
    Column("authorization_required", Integer, nullable=False),
    Column("confidence", Float),
    Column("status", Text, nullable=False),
    Column("generated_at", Text, nullable=False),
    Column("metadata", Text, nullable=False),
)

# --- Identity and access management (ADR-012) ---------------------------
# Isolated Phase 1 slice: these tables are persisted and unit-tested but not
# yet consulted by any route/command. See docs/TO-DO.md Priority 1.

users_table = Table(
    "users",
    metadata,
    Column("id", Text, primary_key=True),
    Column("username", Text, nullable=False, unique=True),
    Column("email", Text),
    Column("password_hash", Text, nullable=False),
    Column("is_superuser", Integer, nullable=False),
    Column("is_active", Integer, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

access_roles_table = Table(
    "access_roles",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text, nullable=False),
)

permissions_table = Table(
    "permissions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("key", Text, nullable=False, unique=True),
    Column("description", Text, nullable=False),
)

role_permissions_table = Table(
    "role_permissions",
    metadata,
    Column("role_id", Text, ForeignKey("access_roles.id"), primary_key=True),
    Column("permission_id", Text, ForeignKey("permissions.id"), primary_key=True),
)

user_roles_table = Table(
    "user_roles",
    metadata,
    Column("user_id", Text, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Text, ForeignKey("access_roles.id"), primary_key=True),
)

user_permissions_table = Table(
    "user_permissions",
    metadata,
    Column("user_id", Text, ForeignKey("users.id"), primary_key=True),
    Column("permission_id", Text, ForeignKey("permissions.id"), primary_key=True),
)

refresh_tokens_table = Table(
    "refresh_tokens",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", Text, ForeignKey("users.id"), nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("issued_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
    Column("revoked_at", Text),
)

# --- Project<->User connection reference (docs/TO-DO.md Priority 1) -----
# A lightweight, informational record of which user connected which
# project -- NOT an access-control boundary (nothing enforces anything
# based on it yet; that is the deliberately deferred broader refactor).
# Lives alongside `projects_table` (same database as the request's
# resolved `database_url`), not in the identity migration/database,
# because it is per-project metadata like `tasks`/`executions`/etc, not
# an identity concern -- unlike identity, which always resolves through
# the primary configured database. No FK on `user_id`: the project's
# database and the primary identity database are not guaranteed to be
# the same database when `database_url` is overridden per-request.
project_connections_table = Table(
    "project_connections",
    metadata,
    Column("project_id", Text, ForeignKey("projects.id"), primary_key=True),
    Column("user_id", Text, primary_key=True),
    Column("connected_at", Text, nullable=False),
)

# --- Conversations (ADR-014) --------------------------------------------
# A bounded context independent of tasks/executions -- see
# domain/conversations/entities.py. `module_id` has no FK: modules are a
# code-defined vocabulary (ADR-015), not a database table.
conversations_table = Table(
    "conversations",
    metadata,
    Column("id", Text, primary_key=True),
    Column("module_id", Text, nullable=False),
    Column("project_id", Text, ForeignKey("projects.id")),
    Column("title", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("archived", Integer, nullable=False),
)

messages_table = Table(
    "messages",
    metadata,
    Column("id", Text, primary_key=True),
    Column("conversation_id", Text, ForeignKey("conversations.id"), nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("error", Text),
    Column("provider_name", Text, nullable=False),
    Column("model_id", Text),
    Column("linked_task_id", Text, ForeignKey("tasks.id")),
    Column("linked_execution_id", Text, ForeignKey("executions.id")),
    Column("resource_usage", Text, nullable=False),
)

automatic_policy_table = Table(
    "automatic_policy",
    metadata,
    Column("id", Text, primary_key=True),
    Column("allowed_operations", Text, nullable=False),
    Column("allowed_cross_role_transitions", Text, nullable=False),
    Column("allow_model_substitution", Integer, nullable=False),
    Column("allow_context_expansion", Integer, nullable=False),
    Column("updated_at", Text, nullable=False),
)
