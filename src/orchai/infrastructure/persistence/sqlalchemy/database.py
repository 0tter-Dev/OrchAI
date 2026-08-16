"""SQLAlchemy database connection and migration runner."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class SQLAlchemyDatabase:
    """Database boundary shared by SQLite and PostgreSQL SQLAlchemy repositories."""

    def __init__(self, url: str) -> None:
        self.url = _normalize_url(url)
        _ensure_sqlite_parent(self.url)
        self.engine = create_engine(self.url, future=True)

    def migrate(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            for migration in _migration_files():
                version = migration.name.split("_", maxsplit=1)[0]
                applied = connection.execute(
                    text("SELECT 1 FROM schema_migrations WHERE version = :version"),
                    {"version": version},
                ).first()
                if applied is not None:
                    continue
                for statement in _split_sql(migration.read_text(encoding="utf-8")):
                    connection.exec_driver_sql(statement)
                connection.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                    {"version": version},
                )


def _normalize_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw_path = url.removeprefix("sqlite:///")
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def _migration_files() -> tuple[resources.abc.Traversable, ...]:
    migration_root = resources.files("orchai.infrastructure.persistence.sqlite")
    migration_root = migration_root.joinpath("migrations")
    return tuple(
        sorted(
            (
                child
                for child in migration_root.iterdir()
                if child.name.endswith(".sql")
            ),
            key=lambda child: child.name,
        )
    )


def _split_sql(script: str) -> tuple[str, ...]:
    return tuple(
        statement.strip()
        for statement in script.split(";")
        if statement.strip()
    )


def engine_from_database(database: SQLAlchemyDatabase) -> Engine:
    return database.engine
