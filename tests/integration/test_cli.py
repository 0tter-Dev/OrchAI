from typer.testing import CliRunner

from orchai.interfaces.cli.main import app


def test_cli_local_flow_runs_with_sqlite_database(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "local-flow",
            str(tmp_path),
            "docs/INDEX.md",
            "--title",
            "CLI integration flow",
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "execution_state=COMPLETED" in result.output
    assert f"database={database_url}" in result.output


def test_cli_db_migrate_prepares_sqlite_database(tmp_path) -> None:
    database_path = tmp_path / "orchai.db"
    database_url = f"sqlite:///{database_path}"
    runner = CliRunner()

    result = runner.invoke(app, ["db", "migrate", "--database-url", database_url])

    assert result.exit_code == 0
    assert database_path.exists()
    assert "migrations=applied" in result.output


def test_cli_db_create_requires_postgresql_url() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["db", "create"])

    assert result.exit_code != 0
    assert "requires a PostgreSQL database URL" in result.output
