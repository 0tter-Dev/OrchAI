from typer.testing import CliRunner

from orchai.interfaces.cli.main import app


def test_cli_local_flow_runs_with_sqlite_database(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
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
    assert f"project_id={_output_value(result.output, 'project_id')}" in audit_result.output
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


def test_cli_local_flow_manual_mode_runs_direct_command_without_suggestion(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
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
            "--execution-mode",
            "MANUAL",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "execution_state=COMPLETED" in result.output
    assert "suggestion_id=" in result.output
    assert "suggestion_status=" in result.output
    assert "blocked_reason=" in result.output


def test_cli_local_flow_automatic_mode_runs_with_configured_policy(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
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
            "--execution-mode",
            "AUTOMATIC",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "execution_state=COMPLETED" in result.output
    assert "suggestion_status=ACCEPTED" in result.output
    assert "blocked_reason=" in result.output


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
    assert "provider_sharing=CLOUD_ALLOWED_WITH_AUTHORIZATION" in result.output


def test_cli_projects_readiness_reports_minimum_requirements(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["projects", "readiness", str(tmp_path)])

    assert result.exit_code == 0
    assert "readiness_level=LEVEL_2_VALIDATABLE" in result.output
    assert "has_git=true" in result.output
    assert "has_documentation=true" in result.output


def test_cli_projects_security_reports_derived_profile(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    runner = CliRunner()

    result = runner.invoke(app, ["projects", "security", str(tmp_path)])

    assert result.exit_code == 0
    assert "readiness_level=LEVEL_1_CHANGEABLE" in result.output
    assert "allow_cloud_provider_sharing=false" in result.output
    assert "restricted_areas=credentials,personal_data,private,secrets" in result.output


def test_cli_projects_can_update_persisted_security_profile(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    flow_result = runner.invoke(
        app,
        [
            "local-flow",
            str(tmp_path),
            "docs/INDEX.md",
            "--database-url",
            database_url,
            "--approve-suggestion",
        ],
    )
    assert flow_result.exit_code == 0
    project_id = _output_value(flow_result.output, "project_id")

    update_result = runner.invoke(
        app,
        [
            "projects",
            "update-security",
            project_id,
            "--database-url",
            database_url,
            "--allow-cloud-provider-sharing",
            "true",
            "--persist-context-snapshots",
            "true",
            "--allow-git-bootstrap",
            "true",
            "--readiness-level",
            "LEVEL_3_AUTOMATABLE",
        ],
    )

    assert update_result.exit_code == 0
    assert "updated=true" in update_result.output
    assert "allow_cloud_provider_sharing=true" in update_result.output
    assert "readiness_level=LEVEL_3_AUTOMATABLE" in update_result.output

    show_result = runner.invoke(
        app,
        [
            "projects",
            "show",
            project_id,
            "--database-url",
            database_url,
        ],
    )
    list_result = runner.invoke(
        app,
        [
            "projects",
            "list",
            "--database-url",
            database_url,
        ],
    )

    assert show_result.exit_code == 0
    assert "allow_cloud_provider_sharing=true" in show_result.output
    assert "persist_context_snapshots=true" in show_result.output
    assert "allow_git_bootstrap=true" in show_result.output
    assert "effective_readiness_level=LEVEL_3_AUTOMATABLE" in show_result.output
    assert list_result.exit_code == 0
    assert f"project_id={project_id}" in list_result.output
    assert "allow_cloud_provider_sharing=true" in list_result.output


def test_cli_projects_show_observed_and_effective_readiness(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    first_flow = runner.invoke(
        app,
        [
            "local-flow",
            str(tmp_path),
            "docs/INDEX.md",
            "--database-url",
            database_url,
            "--approve-suggestion",
        ],
    )
    project_id = _output_value(first_flow.output, "project_id")
    runner.invoke(
        app,
        [
            "projects",
            "update-security",
            project_id,
            "--database-url",
            database_url,
            "--readiness-level",
            "LEVEL_3_AUTOMATABLE",
        ],
    )
    second_flow = runner.invoke(
        app,
        [
            "local-flow",
            str(tmp_path),
            "docs/INDEX.md",
            "--database-url",
            database_url,
            "--approve-suggestion",
        ],
    )
    assert second_flow.exit_code == 0
    assert _output_value(second_flow.output, "project_id") == project_id

    show_result = runner.invoke(
        app,
        ["projects", "show", project_id, "--database-url", database_url],
    )

    assert show_result.exit_code == 0
    assert "effective_readiness_level=LEVEL_3_AUTOMATABLE" in show_result.output
    assert "observed_readiness_level=LEVEL_2_VALIDATABLE" in show_result.output


def test_cli_projects_operate_writes_through_orchestration(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "projects",
            "operate",
            str(tmp_path),
            "WRITE_SOURCE",
            "--database-url",
            database_url,
            "--resource",
            "src/app.py",
            "--content",
            "print('hello')",
            "--approve-operation",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "project_operation=WRITE_SOURCE" in result.output
    assert "blocked_reason=" in result.output
    assert (tmp_path / "src" / "app.py").read_text(encoding="utf-8") == "print('hello')"


def test_cli_projects_operate_blocks_without_approval(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "projects",
            "operate",
            str(tmp_path),
            "WRITE_SOURCE",
            "--database-url",
            database_url,
            "--resource",
            "src/app.py",
            "--content",
            "print('hello')",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=PLANNED" in result.output
    assert "blocked_reason=suggested_mode_requires_approval" in result.output
    assert not (tmp_path / "src" / "app.py").exists()


def test_cli_projects_operate_manual_mode_runs_explicit_operation(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "projects",
            "operate",
            str(tmp_path),
            "WRITE_SOURCE",
            "--database-url",
            database_url,
            "--resource",
            "src/manual.py",
            "--content",
            "print('manual')",
            "--execution-mode",
            "MANUAL",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "blocked_reason=" in result.output
    assert (tmp_path / "src" / "manual.py").read_text(encoding="utf-8") == "print('manual')"


def test_cli_projects_operate_automatic_mode_runs_configured_operation(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "projects",
            "operate",
            str(tmp_path),
            "WRITE_SOURCE",
            "--database-url",
            database_url,
            "--resource",
            "src/automatic.py",
            "--content",
            "print('automatic')",
            "--execution-mode",
            "AUTOMATIC",
        ],
    )

    assert result.exit_code == 0
    assert "task_state=IMPLEMENTED" in result.output
    assert "blocked_reason=" in result.output
    assert (tmp_path / "src" / "automatic.py").read_text(encoding="utf-8") == "print('automatic')"


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
