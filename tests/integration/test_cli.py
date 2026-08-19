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
            "--approve-suggestion",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "execution_state=COMPLETED" in result.output
    assert "suggestion_status=ACCEPTED" in result.output
    assert "audit_records=" in result.output
    assert f"database={database_url}" in result.output

    task_id = _output_value(result.output, "task_id")
    audit_result = runner.invoke(
        app,
        [
            "audit",
            "list",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--limit",
            "5",
        ],
    )
    events_result = runner.invoke(
        app,
        [
            "events",
            "list",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--limit",
            "5",
        ],
    )

    assert audit_result.exit_code == 0
    assert "operation=EXECUTION_COMPLETED" in audit_result.output
    assert events_result.exit_code == 0
    assert "event_type=EXECUTION_COMPLETED" in events_result.output

    metrics_result = runner.invoke(
        app,
        [
            "metrics",
            "list",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--limit",
            "10",
        ],
    )
    suggestions_result = runner.invoke(
        app,
        [
            "suggestions",
            "list",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--limit",
            "5",
        ],
    )

    assert metrics_result.exit_code == 0
    assert "name=execution.success" in metrics_result.output
    assert suggestions_result.exit_code == 0
    assert "status=ACCEPTED" in suggestions_result.output


def test_cli_local_flow_suggested_mode_requires_approval(tmp_path) -> None:
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
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "task_state=PLANNED" in result.output
    assert "execution_id=" in result.output
    assert "suggestion_status=PRESENTED" in result.output
    assert "blocked_reason=suggested_mode_requires_approval" in result.output


def test_cli_db_migrate_prepares_sqlite_database(tmp_path) -> None:
    database_path = tmp_path / "orchai.db"
    database_url = f"sqlite:///{database_path}"
    runner = CliRunner()

    result = runner.invoke(app, ["db", "migrate", "--database-url", database_url])

    assert result.exit_code == 0
    assert database_path.exists()
    assert "migrations=applied" in result.output


def test_cli_projects_discover_uses_filesystem_adapter(tmp_path) -> None:
    (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "projects",
            "discover",
            str(tmp_path),
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "adapter_type=local_filesystem" in result.output
    assert "resource=README.md" in result.output


def test_cli_db_create_requires_postgresql_url(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ORCHAI_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["db", "create"])

    assert result.exit_code != 0
    assert "requires a PostgreSQL database URL" in result.output


def _output_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing output key: {key}")
