import pytest

from orchai.infrastructure.persistence.postgresql.admin import parse_postgresql_target


def test_parse_postgresql_target_uses_postgres_maintenance_database() -> None:
    target = parse_postgresql_target(
        "postgresql://postgres:secret@localhost:5432/orchai"
    )

    assert target.database_name == "orchai"
    assert target.target_url == "postgresql://postgres:secret@localhost:5432/orchai"
    assert target.maintenance_url == "postgresql://postgres:secret@localhost:5432/postgres"


def test_parse_postgresql_target_normalizes_sqlalchemy_psycopg_url() -> None:
    target = parse_postgresql_target(
        "postgresql+psycopg://postgres:secret@localhost:5432/orchai",
        maintenance_database="template1",
    )

    assert target.target_url == "postgresql://postgres:secret@localhost:5432/orchai"
    assert target.maintenance_url == "postgresql://postgres:secret@localhost:5432/template1"


def test_parse_postgresql_target_rejects_non_postgresql_url() -> None:
    with pytest.raises(ValueError):
        parse_postgresql_target("sqlite:///orchai.db")
