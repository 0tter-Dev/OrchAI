from sqlalchemy import text

from orchai.infrastructure.persistence import SQLAlchemyDatabase


def test_sqlalchemy_database_applies_migrations_once(tmp_path) -> None:
    database = SQLAlchemyDatabase(f"sqlite:///{tmp_path / 'orchai.db'}")

    database.migrate()
    database.migrate()

    with database.engine.begin() as connection:
        versions = connection.execute(
            text("SELECT version FROM schema_migrations ORDER BY version")
        ).all()

    assert [row[0] for row in versions] == ["0001", "0002", "0003", "0004"]
