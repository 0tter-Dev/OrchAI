"""Minimal OrchAI CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import typer

from orchai.application.projects import UpdateProjectSecurityCommand
from orchai.application.orchestration import run_local_flow, run_project_operation
from orchai.bootstrap import (
    build_sqlalchemy_local_flow_dependencies,
    build_sqlalchemy_runtime,
)
from orchai.domain.identifiers import ProjectId, TaskId
from orchai.domain.projects import ProjectOperation, ProjectReadinessLevel, ProviderTarget
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
    provider_target: ProviderTarget = typer.Option(
        ProviderTarget.LOCAL,
        "--provider-target",
        case_sensitive=False,
        help="Treat the execution as local or cloud for project security policy.",
    ),
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
            provider_target=provider_target,
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
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter audit records by project id.",
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
            project_id=ProjectId(project_id) if project_id is not None else None,
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
                    f"project_id={record.project_id or ''}",
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
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter events by project id.",
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
            project_id=ProjectId(project_id) if project_id is not None else None,
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
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter metrics by project id.",
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
            project_id=ProjectId(project_id) if project_id is not None else None,
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
                    f"project_id={record.project_id or ''}",
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
                    f"provider_sharing={resource.provider_sharing_level.value}",
                    f"persistence={resource.persistence_classification.value}",
                    f"restricted={str(resource.restricted).lower()}",
                    "capabilities="
                    + ",".join(
                        capability.value for capability in resource.capabilities
                    ),
                )
            )
        )


@projects_app.command("readiness")
def project_readiness(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
) -> None:
    """Assess project readiness through a Project Adapter."""

    adapter = LocalFilesystemProjectAdapter(project_root)
    readiness = asyncio.run(adapter.assess_readiness())
    typer.echo(f"readiness_level={readiness.readiness_level.value}")
    typer.echo(f"has_git={str(readiness.has_git).lower()}")
    typer.echo(f"has_documentation={str(readiness.has_documentation).lower()}")
    typer.echo(f"has_tests={str(readiness.has_tests).lower()}")
    typer.echo("reasons=" + ",".join(readiness.reasons))


@projects_app.command("security")
def project_security(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
) -> None:
    """Inspect the derived project security profile."""

    adapter = LocalFilesystemProjectAdapter(project_root)
    readiness = asyncio.run(adapter.assess_readiness())
    profile = readiness.security_profile
    typer.echo(f"readiness_level={profile.readiness_level.value}")
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(profile.allow_cloud_provider_sharing).lower()
    )
    typer.echo("access_scope=" + ",".join(profile.access_scope))
    typer.echo("restricted_areas=" + ",".join(profile.restricted_areas))


@projects_app.command("operate")
def operate_project(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
    operation: ProjectOperation = typer.Argument(
        ...,
        case_sensitive=False,
        help="Protected project operation to run.",
    ),
    title: str = typer.Option("Protected project operation", help="Task title."),
    resource: str = typer.Option(
        "",
        "--resource",
        help="Relative project resource for read/write operations.",
    ),
    content: str = typer.Option(
        "",
        "--content",
        help="Content used by write operations.",
    ),
    command: str = typer.Option(
        "",
        "--command",
        help="Space-separated bounded command for RUN_COMMAND/RUN_VALIDATION.",
    ),
    test_args: str = typer.Option(
        "",
        "--test-args",
        help="Space-separated pytest args for RUN_TESTS.",
    ),
    approve_operation: bool = typer.Option(
        False,
        "--approve-operation/--no-approve-operation",
        help="Explicitly approve this operation in SUGGESTED mode.",
    ),
    execution_mode: ExecutionMode = typer.Option(
        ExecutionMode.SUGGESTED,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode enforced by the Orchestrator.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """Run a protected project operation through orchestration."""

    _validate_project_operation_input(
        operation=operation,
        resource=resource,
        content=content,
        command=command,
    )
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    result = asyncio.run(
        run_project_operation(
            project_root=project_root,
            operation=operation,
            title=title,
            resource=resource,
            content=content,
            command=_split_words(command),
            test_args=_split_words(test_args),
            approve_operation=approve_operation,
            execution_mode=execution_mode,
            dependencies=build_sqlalchemy_local_flow_dependencies(url),
            storage_label=_safe_database_label(url),
        )
    )
    typer.echo(f"project_id={result['project_id']}")
    typer.echo(f"task_id={result['task_id']}")
    typer.echo(f"authorization_id={result['authorization_id']}")
    typer.echo(f"task_state={result['task_state']}")
    typer.echo(f"project_operation={result['project_operation']}")
    typer.echo(f"resource={result['resource']}")
    typer.echo(f"exit_code={result['exit_code']}")
    typer.echo(f"blocked_reason={result['blocked_reason']}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"audit_records={result['audit_records']}")
    typer.echo(f"database={result['database']}")
    if result["output"]:
        typer.echo("output=" + result["output"].replace("\n", "\\n"))


@projects_app.command("list")
def list_projects(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """List persisted project configurations."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    projects = asyncio.run(runtime.project_service.list_projects())
    typer.echo(f"projects={len(projects)}")
    for project in projects:
        typer.echo(
            " ".join(
                (
                    f"project_id={project.id}",
                    f"name={project.name}",
                    f"effective_readiness_level={project.readiness_level.value}",
                    "observed_readiness_level="
                    + project.observed_readiness_level.value,
                    "allow_cloud_provider_sharing="
                    + str(
                        project.security_profile.allow_cloud_provider_sharing
                    ).lower(),
                    "persist_context_snapshots="
                    + str(
                        project.security_profile.persist_context_snapshots
                    ).lower(),
                )
            )
        )


@projects_app.command("show")
def show_project(
    project_id: str = typer.Argument(..., help="Persisted project id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """Show one persisted project configuration."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    project = asyncio.run(runtime.project_service.get_project(ProjectId(project_id)))
    profile = project.security_profile
    typer.echo(f"project_id={project.id}")
    typer.echo(f"name={project.name}")
    typer.echo(f"root_location={project.root_location}")
    typer.echo(f"adapter_type={project.adapter_type}")
    typer.echo(f"effective_readiness_level={project.readiness_level.value}")
    typer.echo(f"observed_readiness_level={project.observed_readiness_level.value}")
    typer.echo("access_scope=" + ",".join(profile.access_scope))
    typer.echo("restricted_areas=" + ",".join(profile.restricted_areas))
    typer.echo("sensitive_patterns=" + ",".join(profile.sensitive_patterns))
    typer.echo("allow_git_bootstrap=" + str(profile.allow_git_bootstrap).lower())
    typer.echo(
        "allow_architecture_restructure="
        + str(profile.allow_architecture_restructure).lower()
    )
    typer.echo("allow_cicd_changes=" + str(profile.allow_cicd_changes).lower())
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(profile.allow_cloud_provider_sharing).lower()
    )
    typer.echo(
        "persist_architecture_summaries="
        + str(profile.persist_architecture_summaries).lower()
    )
    typer.echo(
        "persist_naming_summaries=" + str(profile.persist_naming_summaries).lower()
    )
    typer.echo(
        "persist_functional_summaries="
        + str(profile.persist_functional_summaries).lower()
    )
    typer.echo(
        "persist_context_snapshots="
        + str(profile.persist_context_snapshots).lower()
    )
    typer.echo(
        "observed_access_scope="
        + ",".join(project.observed_security_profile.access_scope)
    )


@projects_app.command("update-security")
def update_project_security(
    project_id: str = typer.Argument(..., help="Persisted project id."),
    readiness_level: ProjectReadinessLevel | None = typer.Option(
        None,
        "--readiness-level",
        case_sensitive=False,
        help="Override the persisted readiness level for the project.",
    ),
    access_scope: str | None = typer.Option(
        None,
        "--access-scope",
        help="Comma-separated access scope values.",
    ),
    restricted_areas: str | None = typer.Option(
        None,
        "--restricted-areas",
        help="Comma-separated restricted area names.",
    ),
    sensitive_patterns: str | None = typer.Option(
        None,
        "--sensitive-patterns",
        help="Comma-separated sensitive path/name patterns.",
    ),
    allow_git_bootstrap: str | None = typer.Option(
        None,
        "--allow-git-bootstrap",
        help="Allow OrchAI to initialize or fix Git when explicitly requested.",
    ),
    allow_architecture_restructure: str | None = typer.Option(
        None,
        "--allow-architecture-restructure",
        help="Allow architecture/base-structure changes when explicitly requested.",
    ),
    allow_cicd_changes: str | None = typer.Option(
        None,
        "--allow-cicd-changes",
        help="Allow CI/CD changes when explicitly requested.",
    ),
    allow_cloud_provider_sharing: str | None = typer.Option(
        None,
        "--allow-cloud-provider-sharing",
        help="Allow authorized context to cross a cloud provider boundary.",
    ),
    persist_architecture_summaries: str | None = typer.Option(
        None,
        "--persist-architecture-summaries",
        help="Allow persistence of architecture summaries.",
    ),
    persist_naming_summaries: str | None = typer.Option(
        None,
        "--persist-naming-summaries",
        help="Allow persistence of naming summaries.",
    ),
    persist_functional_summaries: str | None = typer.Option(
        None,
        "--persist-functional-summaries",
        help="Allow persistence of functional summaries.",
    ),
    persist_context_snapshots: str | None = typer.Option(
        None,
        "--persist-context-snapshots",
        help="Allow persistence of bounded context snapshots.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL or local SQLite.",
    ),
) -> None:
    """Update one persisted project security/readiness profile."""

    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    project = asyncio.run(
        runtime.project_service.update_security_profile(
            UpdateProjectSecurityCommand(
                project_id=ProjectId(project_id),
                readiness_level=readiness_level,
                access_scope=_parse_csv_tuple(access_scope),
                restricted_areas=_parse_csv_tuple(restricted_areas),
                sensitive_patterns=_parse_csv_tuple(sensitive_patterns),
                allow_git_bootstrap=_parse_optional_bool(allow_git_bootstrap),
                allow_architecture_restructure=_parse_optional_bool(
                    allow_architecture_restructure
                ),
                allow_cicd_changes=_parse_optional_bool(allow_cicd_changes),
                allow_cloud_provider_sharing=_parse_optional_bool(
                    allow_cloud_provider_sharing
                ),
                persist_architecture_summaries=_parse_optional_bool(
                    persist_architecture_summaries
                ),
                persist_naming_summaries=_parse_optional_bool(
                    persist_naming_summaries
                ),
                persist_functional_summaries=_parse_optional_bool(
                    persist_functional_summaries
                ),
                persist_context_snapshots=_parse_optional_bool(
                    persist_context_snapshots
                ),
            )
        )
    )
    typer.echo(f"project_id={project.id}")
    typer.echo(f"effective_readiness_level={project.readiness_level.value}")
    typer.echo(f"observed_readiness_level={project.observed_readiness_level.value}")
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(project.security_profile.allow_cloud_provider_sharing).lower()
    )
    typer.echo(
        "persist_context_snapshots="
        + str(project.security_profile.persist_context_snapshots).lower()
    )
    typer.echo("updated=true")


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


def _parse_csv_tuple(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise typer.BadParameter(f"invalid boolean value: {value}")


def _split_words(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.split() if part)


def _validate_project_operation_input(
    *,
    operation: ProjectOperation,
    resource: str,
    content: str,
    command: str,
) -> None:
    if operation in {
        ProjectOperation.WRITE_SOURCE,
        ProjectOperation.WRITE_DOCUMENTATION,
    }:
        if not resource.strip():
            raise typer.BadParameter("write operations require --resource")
        if not content:
            raise typer.BadParameter("write operations require --content")
    if operation in {
        ProjectOperation.RUN_COMMAND,
        ProjectOperation.RUN_VALIDATION,
    } and not command.strip():
        raise typer.BadParameter(f"{operation.value} requires --command")


if __name__ == "__main__":
    app()
