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
