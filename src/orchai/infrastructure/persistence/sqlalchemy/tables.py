"""SQLAlchemy table definitions for OrchAI persistence."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, Text

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

