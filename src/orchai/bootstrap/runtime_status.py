"""Operational runtime status helpers shared by CLI and API."""

from __future__ import annotations

from typing import Any

from orchai.application.executions.ports import AIProviderPort
from orchai.infrastructure.configuration import OrchAISettings
from orchai.infrastructure.persistence import SQLAlchemyDatabase


async def collect_runtime_status(
    *,
    settings: OrchAISettings,
    provider: AIProviderPort,
    database: SQLAlchemyDatabase,
) -> dict[str, Any]:
    """Collect a consolidated operational runtime status."""

    database_status = _check_database(database)
    provider_health = await provider.healthcheck()

    warnings: list[str] = []
    if settings.database.is_sqlite:
        warnings.append(
            "SQLite is a secondary option for fast local/test operation only; "
            "PostgreSQL is the explicit production default."
        )
    if not provider_health.reachable:
        warnings.append("Configured AI provider is not reachable.")
    if settings.ai_provider.provider == "openai" and settings.ai_provider.api_key is None:
        warnings.append("OpenAI provider selected without ORCHAI_AI_API_KEY configured.")

    ready = database_status["reachable"] and provider_health.reachable
    if settings.database.is_sqlite:
        operational_mode = "local-only"
    elif ready:
        operational_mode = "shared-ready"
    else:
        operational_mode = "shared-degraded"

    return {
        "ready": ready,
        "operational_mode": operational_mode,
        "recommended_operational_dialect": "postgresql",
        "warnings": warnings,
        "database": {
            "url": _safe_database_label(settings.database.sqlalchemy_url),
            "dialect": settings.database.dialect,
            "is_postgresql": settings.database.is_postgresql,
            "is_sqlite": settings.database.is_sqlite,
            **database_status,
        },
        "provider": {
            "provider": provider_health.provider_name,
            "configured_provider": settings.ai_provider.provider,
            "configured_model": settings.ai_provider.model,
            "reachable": provider_health.reachable,
            "message": provider_health.message,
            "metadata": dict(provider_health.metadata),
        },
        "api": {
            "host": settings.api.host,
            "port": settings.api.port,
        },
    }


def _check_database(database: SQLAlchemyDatabase) -> dict[str, Any]:
    try:
        database.ping()
    except Exception as exc:  # pragma: no cover - exercised through integration
        return {"reachable": False, "message": str(exc)}
    return {"reachable": True, "message": "Database connection succeeded."}


def _safe_database_label(url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

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
