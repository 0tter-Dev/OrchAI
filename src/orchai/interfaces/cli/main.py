"""Minimal OrchAI CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import typer

from orchai.application.orchestration import run_local_flow
from orchai.bootstrap import (
    build_sqlalchemy_local_flow_dependencies,
    build_sqlalchemy_runtime,
)
from orchai.domain.identifiers import TaskId
from orchai.domain.tasks import ExecutionMode
from orchai.infrastructure.configuration import load_settings
from orchai.infrastructure.persistence import SQLAlchemyDatabase
from orchai.infrastructure.persistence.postgresql import PostgreSQLDatabaseAdmin
from orchai.infrastructure.projects import LocalFilesystemProjectAdapter

app = typer.Typer(help="OrchAI orchestration CLI.")
db_app = typer.Typer(help="Database operations.")
audit_app = typer.Typer(help="Audit history operations.")
events_app = typer.Typer(help="Event history operations.")
metrics_app = typer.Typer(help="Operational metrics operations.")
suggestions_app = typer.Typer(help="Suggestion operations.")
projects_app = typer.Typer(help="Project adapter operations.")
app.add_typer(db_app, name="db")
app.add_typer(audit_app, name="audit")
app.add_typer(events_app, name="events")
app.add_typer(metrics_app, name="metrics")
app.add_typer(suggestions_app, name="suggestions")
app.add_typer(projects_app, name="projects")


@db_app.command("migrate")
def migrate(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """Apply pending database migrations."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    SQLAlchemyDatabase(url).migrate()
    typer.echo(f"database={_safe_database_label(url)}")
    typer.echo("migrations=applied")


@db_app.command("create")
def create_database(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="PostgreSQL database URL. Defaults to ORCHAI_DATABASE_URL.",
    ),
    maintenance_database: str = typer.Option(
        "postgres",
        "--maintenance-database",
        help="Existing database used to create the target database.",
    ),
) -> None:
    """Create a PostgreSQL database when it does not exist."""

    settings = load_settings()
    url = database_url or settings.database.url
    if not settings.database.is_postgresql and database_url is None:
        raise typer.BadParameter("db create requires a PostgreSQL database URL")

    created = PostgreSQLDatabaseAdmin(
        url,
        maintenance_database=maintenance_database,
    ).create_database()
    status = "created" if created else "already_exists"
    typer.echo(f"database={_safe_database_label(url)}")
    typer.echo(f"status={status}")


@app.command("local-flow")
def local_flow(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the project adapter.",
    ),
    context_path: str = typer.Argument(
        ...,
        help="Relative file path to authorize and resolve as execution context.",
    ),
    title: str = typer.Option("CLI local flow", help="Task title."),
    model: str = typer.Option("local-demo", help="Provider-independent model id."),
    execution_mode: ExecutionMode = typer.Option(
        ExecutionMode.SUGGESTED,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode enforced by the Orchestrator.",
    ),
    approve_suggestion: bool = typer.Option(
        False,
        "--approve-suggestion/--no-approve-suggestion",
        help="Explicitly approve the generated suggestion in SUGGESTED mode.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """Run a minimal authorized task/execution/context flow."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    result = asyncio.run(
        run_local_flow(
            project_root=project_root,
            context_path=context_path,
            title=title,
            model=model,
            dependencies=build_sqlalchemy_local_flow_dependencies(url),
            storage_label=_safe_database_label(url),
            execution_mode=execution_mode,
            approve_suggestion=approve_suggestion,
        )
    )
    typer.echo(f"project_id={result['project_id']}")
    typer.echo(f"task_id={result['task_id']}")
    typer.echo(f"authorization_id={result['authorization_id']}")
    typer.echo(f"execution_id={result['execution_id']}")
    typer.echo(f"task_state={result['task_state']}")
    typer.echo(f"execution_state={result['execution_state']}")
    typer.echo(f"suggestion_id={result['suggestion_id']}")
    typer.echo(f"suggested_role={result['suggested_role']}")
    typer.echo(f"suggested_action={result['suggested_action']}")
    typer.echo(f"suggestion_status={result['suggestion_status']}")
    typer.echo(f"blocked_reason={result['blocked_reason']}")
    typer.echo(f"context_items={result['context_items']}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"audit_records={result['audit_records']}")
    typer.echo(f"database={result['database']}")


@audit_app.command("list")
def list_audit_records(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter audit records by task id.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """List persisted audit records."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    records = asyncio.run(
        runtime.audit_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            limit=limit,
        )
    )
    for record in records:
        typer.echo(
            " ".join(
                (
                    f"audit_id={record.id}",
                    f"occurred_at={record.occurred_at.isoformat()}",
                    f"operation={record.operation}",
                    f"outcome={record.outcome}",
                    f"actor={record.actor}",
                    f"task_id={record.task_id or ''}",
                    f"execution_id={record.execution_id or ''}",
                    f"authorization_id={record.authorization_id or ''}",
                    f"event_id={record.event_id or ''}",
                )
            )
        )


@events_app.command("list")
def list_events(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter events by task id.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """List persisted domain events."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    events = asyncio.run(
        runtime.event_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            limit=limit,
        )
    )
    for event in events:
        typer.echo(
            " ".join(
                (
                    f"event_id={event.event_id}",
                    f"occurred_at={event.occurred_at.isoformat()}",
                    f"event_type={event.event_type.value}",
                    f"source={event.source}",
                    f"task_id={event.task_id or ''}",
                    f"project_id={event.project_id or ''}",
                    f"execution_id={event.execution_id or ''}",
                )
            )
        )


@metrics_app.command("list")
def list_metrics(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter metrics by task id.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """List persisted operational metrics."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    records = asyncio.run(
        runtime.metrics_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            limit=limit,
        )
    )
    for record in records:
        typer.echo(
            " ".join(
                (
                    f"metric_id={record.id}",
                    f"observed_at={record.observed_at.isoformat()}",
                    f"name={record.name}",
                    f"value={record.value}",
                    f"unit={record.unit}",
                    f"task_id={record.task_id or ''}",
                    f"execution_id={record.execution_id or ''}",
                )
            )
        )


@suggestions_app.command("list")
def list_suggestions(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter suggestions by task id.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """List persisted suggestions."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    suggestions = asyncio.run(
        runtime.suggestion_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            limit=limit,
        )
    )
    for suggestion in suggestions:
        typer.echo(
            " ".join(
                (
                    f"suggestion_id={suggestion.id}",
                    f"generated_at={suggestion.generated_at.isoformat()}",
                    f"status={suggestion.status.value}",
                    f"role={suggestion.suggested_role.value}",
                    f"action={suggestion.suggested_action.value}",
                    f"confidence={suggestion.confidence or ''}",
                    f"task_id={suggestion.task_id}",
                )
            )
        )


@projects_app.command("discover")
def discover_project(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
) -> None:
    """Discover project resources through a Project Adapter."""

    adapter = LocalFilesystemProjectAdapter(project_root)
    discovery = asyncio.run(adapter.discover(limit=limit))
    typer.echo(f"adapter_type={discovery.metadata.get('adapter_type', '')}")
    typer.echo(f"resources={len(discovery.resources)}")
    for resource in discovery.resources:
        typer.echo(
            " ".join(
                (
                    f"resource={resource.resource}",
                    f"source={resource.source.value}",
                    "capabilities="
                    + ",".join(
                        capability.value for capability in resource.capabilities
                    ),
                )
            )
        )


def _safe_database_label(url: str) -> str:
    parts = urlsplit(url)
    if parts.password is None:
        return url

    userinfo = parts.username or ""
    if userinfo:
        userinfo = f"{userinfo}:***"

    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"

    return urlunsplit(
        (
            parts.scheme,
            f"{userinfo}@{host}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


if __name__ == "__main__":
    app()
