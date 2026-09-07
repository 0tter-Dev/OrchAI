import pytest

from orchai.infrastructure.configuration import load_settings
from orchai.infrastructure.configuration.settings import AuthSettings, DatabaseSettings


def test_load_settings_uses_postgresql_production_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ORCHAI_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = load_settings()

    assert settings.database.url == DatabaseSettings.DEFAULT_URL
    assert settings.database.is_postgresql


def test_load_settings_reads_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_DATABASE_URL", "sqlite:///custom.db")

    settings = load_settings()

    assert settings.database.url == "sqlite:///custom.db"


def test_load_settings_accepts_sqlite_shorthand_alias_for_local_and_test_runs(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ORCHAI_DATABASE_URL", "sqlite")

    settings = load_settings()

    assert settings.database.url == DatabaseSettings.LOCAL_TEST_URL
    assert settings.database.is_sqlite


def test_load_settings_reads_database_url_from_dotenv(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ORCHAI_DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ORCHAI_DATABASE_URL=postgresql://orchai:secret@localhost:5432/orchai\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file=env_file)

    assert settings.database.is_postgresql
    assert settings.database.url.startswith("postgresql://orchai:")


def test_load_settings_normalizes_postgresql_url_for_sqlalchemy(monkeypatch) -> None:
    monkeypatch.setenv(
        "ORCHAI_DATABASE_URL",
        "postgresql://orchai:secret@localhost:5432/orchai",
    )

    settings = load_settings()

    assert settings.database.is_postgresql
    assert settings.database.sqlalchemy_url.startswith("postgresql+psycopg://")


def test_load_settings_reads_ai_provider_and_api_options(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_AI_PROVIDER", "litellm")
    monkeypatch.setenv("ORCHAI_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("ORCHAI_AI_API_KEY", "secret")
    monkeypatch.setenv("ORCHAI_AI_MODEL", "openai/gpt-5")
    monkeypatch.setenv("ORCHAI_AI_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("ORCHAI_API_HOST", "0.0.0.0")
    monkeypatch.setenv("ORCHAI_API_PORT", "9000")

    settings = load_settings()

    assert settings.ai_provider.provider == "litellm"
    assert settings.ai_provider.base_url == "https://api.openai.com/v1"
    assert settings.ai_provider.api_key == "secret"
    assert settings.ai_provider.model == "openai/gpt-5"
    assert settings.ai_provider.timeout_seconds == 45.0
    assert settings.api.host == "0.0.0.0"
    assert settings.api.port == 9000


def test_load_settings_defaults_auth_to_disabled_and_placeholder_secret(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ORCHAI_AUTH_ENFORCED", raising=False)
    monkeypatch.delenv("ORCHAI_AUTH_SECRET_KEY", raising=False)
    monkeypatch.delenv("ORCHAI_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ORCHAI_ADMIN_PASSWORD", raising=False)

    settings = load_settings()

    assert settings.auth.enforced is False
    assert settings.auth.secret_key_is_placeholder
    assert settings.auth.access_token_ttl_minutes == 15
    assert settings.auth.refresh_token_ttl_days == 30
    assert settings.auth.admin_username is None
    assert settings.auth.admin_password is None


def test_load_settings_reads_auth_options_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", "a-real-non-placeholder-secret-key")
    monkeypatch.setenv("ORCHAI_AUTH_ACCESS_TOKEN_TTL_MINUTES", "5")
    monkeypatch.setenv("ORCHAI_AUTH_REFRESH_TOKEN_TTL_DAYS", "7")
    monkeypatch.setenv("ORCHAI_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ORCHAI_ADMIN_PASSWORD", "correct horse battery")

    settings = load_settings()

    assert settings.auth.enforced is True
    assert settings.auth.secret_key == "a-real-non-placeholder-secret-key"
    assert not settings.auth.secret_key_is_placeholder
    assert settings.auth.access_token_ttl_minutes == 5
    assert settings.auth.refresh_token_ttl_days == 7
    assert settings.auth.admin_username == "admin"
    assert settings.auth.admin_password == "correct horse battery"


@pytest.mark.parametrize("bogus_value", ["not-a-bool", "maybe", ""])
def test_load_settings_falls_back_to_default_on_unrecognized_bool_env_value(
    monkeypatch, bogus_value
) -> None:
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", bogus_value)

    settings = load_settings()

    assert settings.auth.enforced is False


def test_auth_settings_rejects_empty_secret_key() -> None:
    with pytest.raises(ValueError, match="secret_key"):
        AuthSettings(secret_key="   ")


@pytest.mark.parametrize(
    "field", ["access_token_ttl_minutes", "refresh_token_ttl_days"]
)
def test_auth_settings_rejects_non_positive_ttls(field) -> None:
    with pytest.raises(ValueError, match="TTL"):
        AuthSettings(**{field: 0})
