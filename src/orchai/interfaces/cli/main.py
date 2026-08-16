"""Minimal OrchAI CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from orchai.application.orchestration import run_local_flow
from orchai.bootstrap import build_sqlalchemy_local_flow_dependencies
from orchai.infrastructure.configuration import load_settings
from orchai.infrastructure.persistence import SQLAlchemyDatabase
from orchai.infrastructure.persistence.postgresql import PostgreSQLDatabaseAdmin

app = typer.Typer(help="OrchAI orchestration CLI.")
db_app = typer.Typer(help="Database operations.")
app.add_typer(db_app, name="db")


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
    typer.echo(f"database={url}")
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
    typer.echo(f"database={url}")
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
            storage_label=url,
        )
    )
    typer.echo(f"project_id={result['project_id']}")
    typer.echo(f"task_id={result['task_id']}")
    typer.echo(f"authorization_id={result['authorization_id']}")
    typer.echo(f"execution_id={result['execution_id']}")
    typer.echo(f"task_state={result['task_state']}")
    typer.echo(f"execution_state={result['execution_state']}")
    typer.echo(f"context_items={result['context_items']}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"database={result['database']}")


if __name__ == "__main__":
    app()
