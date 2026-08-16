"""Configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatabaseSettings(BaseModel):
    """Normalized database configuration."""

    model_config = ConfigDict(frozen=True)

    url: str = Field(default="sqlite:///.orchai/orchai.db")

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

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("database url must not be empty")
        if not normalized.startswith(
            ("sqlite:///", "postgresql://", "postgresql+psycopg://")
        ):
            raise ValueError("database url must be sqlite or postgresql")
        return normalized


class OrchAISettings(BaseModel):
    """Effective application settings."""

    model_config = ConfigDict(frozen=True)

    database: DatabaseSettings


def load_settings() -> OrchAISettings:
    """Load effective settings from environment with safe local defaults."""

    database_url = os.environ.get("ORCHAI_DATABASE_URL", "sqlite:///.orchai/orchai.db")
    return OrchAISettings(database=DatabaseSettings(url=database_url))
