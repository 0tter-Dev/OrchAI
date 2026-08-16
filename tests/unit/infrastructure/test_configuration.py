from orchai.infrastructure.configuration import load_settings


def test_load_settings_uses_sqlite_default(monkeypatch) -> None:
    monkeypatch.delenv("ORCHAI_DATABASE_URL", raising=False)

    settings = load_settings()

    assert settings.database.url == "sqlite:///.orchai/orchai.db"
    assert settings.database.is_sqlite


def test_load_settings_reads_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_DATABASE_URL", "sqlite:///custom.db")

    settings = load_settings()

    assert settings.database.url == "sqlite:///custom.db"


def test_load_settings_normalizes_postgresql_url_for_sqlalchemy(monkeypatch) -> None:
    monkeypatch.setenv(
        "ORCHAI_DATABASE_URL",
        "postgresql://orchai:secret@localhost:5432/orchai",
    )

    settings = load_settings()

    assert settings.database.is_postgresql
    assert settings.database.sqlalchemy_url.startswith("postgresql+psycopg://")
