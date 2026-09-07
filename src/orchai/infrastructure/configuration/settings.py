"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatabaseSettings(BaseModel):
    """Normalized database configuration.

    PostgreSQL is the explicit production default. SQLite remains fully
    supported, but only as a secondary option meant to keep local
    development and automated tests fast and dependency-free. Any code or
    documentation that needs "the default database" should read it from
    here rather than hard-coding a dialect.
    """

    model_config = ConfigDict(frozen=True)

    #: Production-oriented default. Assumes a local PostgreSQL server
    #: reachable with the conventional `orchai`/`orchai` credentials,
    #: matching `orchai db sync` and the project `.env.example`.
    DEFAULT_URL: ClassVar[str] = "postgresql://orchai:orchai@localhost:5432/orchai"

    #: Secondary, zero-dependency option for fast local/test iteration.
    LOCAL_TEST_URL: ClassVar[str] = "sqlite:///.orchai/orchai.db"

    #: Shorthand accepted in `ORCHAI_DATABASE_URL` / `.env` to opt into the
    #: secondary SQLite option without typing the full URL.
    LOCAL_TEST_ALIASES: ClassVar[frozenset[str]] = frozenset({"sqlite", "local"})

    url: str = Field(default=DEFAULT_URL)

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite:///")

    @property
    def is_postgresql(self) -> bool:
        return self.url.startswith(("postgresql://", "postgresql+psycopg://"))

    @property
    def dialect(self) -> Literal["sqlite", "postgresql"]:
        if self.is_sqlite:
            return "sqlite"
        if self.is_postgresql:
            return "postgresql"
        raise ValueError("unsupported database dialect")

    @property
    def sqlalchemy_url(self) -> str:
        if self.url.startswith("postgresql://"):
            return self.url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.url

    @property
    def sqlite_path(self) -> Path:
        if not self.is_sqlite:
            raise ValueError("database url is not a sqlite URL")
        raw_path = self.url.removeprefix("sqlite:///")
        return Path(raw_path).expanduser().resolve()

    @field_validator("url", mode="before")
    @classmethod
    def _expand_local_test_alias(cls, value: str) -> str:
        if isinstance(value, str) and value.strip().lower() in cls.LOCAL_TEST_ALIASES:
            return cls.LOCAL_TEST_URL
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("database url must not be empty")
        if not normalized.startswith(
            ("sqlite:///", "postgresql://", "postgresql+psycopg://")
        ):
            raise ValueError(
                "database url must be sqlite, postgresql, or one of the local/test "
                f"aliases ({', '.join(sorted(cls.LOCAL_TEST_ALIASES))})"
            )
        return normalized


class OrchAISettings(BaseModel):
    """Effective application settings."""

    model_config = ConfigDict(frozen=True)

    database: DatabaseSettings
    ai_provider: AIProviderSettings
    api: APISettings
    auth: AuthSettings


class AIProviderSettings(BaseModel):
    """Normalized AI provider configuration."""

    model_config = ConfigDict(frozen=True)

    #: "litellm" covers every real provider (ADR-013) -- routing between
    #: OpenAI/Anthropic/Gemini/Ollama/etc. is selected by the `model`
    #: field's "<provider>/<model>" prefix, not by this setting.
    provider: Literal["stub", "litellm"] = "stub"
    base_url: str | None = None
    api_key: str | None = None
    organization: str | None = None
    project: str | None = None
    model: str = "local-demo"
    timeout_seconds: float = 120.0

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        return normalized or None

    @field_validator("api_key", "organization", "project", "model")
    @classmethod
    def validate_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class APISettings(BaseModel):
    """Normalized HTTP API settings."""

    model_config = ConfigDict(frozen=True)

    host: str = "127.0.0.1"
    port: int = 8000

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("api host must not be empty")
        return normalized

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("api port must be between 1 and 65535")
        return value


class AuthSettings(BaseModel):
    """Normalized authentication/access-control configuration (ADR-012).

    Landing this configuration (and the enforcement code that reads it) must
    not change behavior for any existing caller by itself -- `enforced`
    defaults to `False` per the rollout plan in
    `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6, so permission
    checks are wired in but inert until deliberately turned on.
    """

    model_config = ConfigDict(frozen=True)

    #: Clearly-marked placeholder, not a real secret -- see
    #: `secret_key_is_placeholder`. Safe as a default because `enforced`
    #: defaults to `False`; a real deployment must override this before
    #: setting `ORCHAI_AUTH_ENFORCED=true`.
    DEFAULT_SECRET_KEY: ClassVar[str] = (
        "orchai-dev-placeholder-secret-key-change-me-before-enforcing"
    )

    enforced: bool = False
    secret_key: str = Field(default=DEFAULT_SECRET_KEY)
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    #: Bootstrap superuser (ADR-012 §8), consumed once by `orchai auth
    #: bootstrap-admin` or first-startup provisioning when zero users exist.
    #: `None` means "not configured" -- the bootstrap path then requires the
    #: username/password to be passed explicitly instead.
    admin_username: str | None = None
    admin_password: str | None = None

    @property
    def secret_key_is_placeholder(self) -> bool:
        """Whether `secret_key` is still the shipped development default."""

        return self.secret_key == self.DEFAULT_SECRET_KEY

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("auth secret_key must not be empty")
        return normalized

    @field_validator("access_token_ttl_minutes", "refresh_token_ttl_days")
    @classmethod
    def validate_positive_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("auth token TTLs must be positive")
        return value


def _parse_bool(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def load_settings(env_file: Path | None = Path(".env")) -> OrchAISettings:
    """Load effective settings from environment with safe local defaults."""

    dotenv_values = _read_dotenv(env_file) if env_file is not None else {}
    database_url = os.environ.get(
        "ORCHAI_DATABASE_URL",
        dotenv_values.get("ORCHAI_DATABASE_URL", DatabaseSettings.DEFAULT_URL),
    )
    provider = os.environ.get(
        "ORCHAI_AI_PROVIDER",
        dotenv_values.get("ORCHAI_AI_PROVIDER", "stub"),
    )
    provider_base_url = os.environ.get(
        "ORCHAI_AI_BASE_URL",
        dotenv_values.get("ORCHAI_AI_BASE_URL"),
    )
    provider_api_key = os.environ.get(
        "ORCHAI_AI_API_KEY",
        dotenv_values.get("ORCHAI_AI_API_KEY"),
    )
    provider_organization = os.environ.get(
        "ORCHAI_AI_ORGANIZATION",
        dotenv_values.get("ORCHAI_AI_ORGANIZATION"),
    )
    provider_project = os.environ.get(
        "ORCHAI_AI_PROJECT",
        dotenv_values.get("ORCHAI_AI_PROJECT"),
    )
    provider_model = os.environ.get(
        "ORCHAI_AI_MODEL",
        dotenv_values.get("ORCHAI_AI_MODEL", "local-demo"),
    )
    provider_timeout_seconds = float(
        os.environ.get(
            "ORCHAI_AI_TIMEOUT_SECONDS",
            dotenv_values.get("ORCHAI_AI_TIMEOUT_SECONDS", "120"),
        )
    )
    api_host = os.environ.get(
        "ORCHAI_API_HOST",
        dotenv_values.get("ORCHAI_API_HOST", "127.0.0.1"),
    )
    api_port = int(
        os.environ.get(
            "ORCHAI_API_PORT",
            dotenv_values.get("ORCHAI_API_PORT", "8000"),
        )
    )
    auth_enforced = _parse_bool(
        os.environ.get(
            "ORCHAI_AUTH_ENFORCED",
            dotenv_values.get("ORCHAI_AUTH_ENFORCED", "false"),
        ),
        default=False,
    )
    auth_secret_key = os.environ.get(
        "ORCHAI_AUTH_SECRET_KEY",
        dotenv_values.get("ORCHAI_AUTH_SECRET_KEY", AuthSettings.DEFAULT_SECRET_KEY),
    )
    auth_access_token_ttl_minutes = int(
        os.environ.get(
            "ORCHAI_AUTH_ACCESS_TOKEN_TTL_MINUTES",
            dotenv_values.get("ORCHAI_AUTH_ACCESS_TOKEN_TTL_MINUTES", "15"),
        )
    )
    auth_refresh_token_ttl_days = int(
        os.environ.get(
            "ORCHAI_AUTH_REFRESH_TOKEN_TTL_DAYS",
            dotenv_values.get("ORCHAI_AUTH_REFRESH_TOKEN_TTL_DAYS", "30"),
        )
    )
    admin_username = os.environ.get(
        "ORCHAI_ADMIN_USERNAME",
        dotenv_values.get("ORCHAI_ADMIN_USERNAME"),
    )
    admin_password = os.environ.get(
        "ORCHAI_ADMIN_PASSWORD",
        dotenv_values.get("ORCHAI_ADMIN_PASSWORD"),
    )
    return OrchAISettings(
        database=DatabaseSettings(url=database_url),
        ai_provider=AIProviderSettings(
            provider=provider,
            base_url=provider_base_url,
            api_key=provider_api_key,
            organization=provider_organization,
            project=provider_project,
            model=provider_model,
            timeout_seconds=provider_timeout_seconds,
        ),
        api=APISettings(host=api_host, port=api_port),
        auth=AuthSettings(
            enforced=auth_enforced,
            secret_key=auth_secret_key,
            access_token_ttl_minutes=auth_access_token_ttl_minutes,
            refresh_token_ttl_days=auth_refresh_token_ttl_days,
            admin_username=admin_username,
            admin_password=admin_password,
        ),
    )


def _read_dotenv(path: Path) -> dict[str, str]:
    dotenv_path = path.expanduser()
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values
