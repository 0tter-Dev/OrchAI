"""PostgreSQL database administration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from psycopg import connect, sql


@dataclass(frozen=True, slots=True)
class PostgreSQLDatabaseTarget:
    """Parsed target and maintenance URLs for a PostgreSQL database."""

    database_name: str
    target_url: str
    maintenance_url: str


class PostgreSQLDatabaseAdmin:
    """Small PostgreSQL administration boundary for local setup."""

    def __init__(self, database_url: str, maintenance_database: str = "postgres") -> None:
        self.target = parse_postgresql_target(
            database_url,
            maintenance_database=maintenance_database,
        )

    def create_database(self) -> bool:
        """Create the target database if it does not exist."""

        with connect(self.target.maintenance_url, autocommit=True) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (self.target.database_name,),
            ).fetchone()
            if exists is not None:
                return False
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(self.target.database_name)
                )
            )
            return True


def parse_postgresql_target(
    database_url: str,
    *,
    maintenance_database: str = "postgres",
) -> PostgreSQLDatabaseTarget:
    normalized = _normalize_postgresql_url(database_url)
    parsed = urlsplit(normalized)
    if parsed.scheme != "postgresql":
        raise ValueError("database URL must use postgresql")

    database_name = parsed.path.lstrip("/")
    if not database_name:
        raise ValueError("database URL must include a target database name")

    maintenance_path = f"/{maintenance_database.strip() or 'postgres'}"
    maintenance_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            maintenance_path,
            parsed.query,
            parsed.fragment,
        )
    )
    return PostgreSQLDatabaseTarget(
        database_name=database_name,
        target_url=normalized,
        maintenance_url=maintenance_url,
    )


def _normalize_postgresql_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return database_url
