import asyncio
import json

from typer.testing import CliRunner

from orchai.application.identity import CreateUserCommand
from orchai.bootstrap import (
    build_identity_runtime_from_settings,
    build_sqlalchemy_runtime,
)
from orchai.domain.identifiers import ExecutionId
from orchai.infrastructure.configuration import load_settings
from orchai.interfaces.cli.main import app

_TEST_SECRET_KEY = "cli-test-secret-key-with-at-least-32-characters"


def _create_user(*, username: str, password: str, is_superuser: bool) -> None:
    """Create a user directly in the identity DB the CLI will read.

    `require_cli_permission` and `orchai auth *` always resolve identity
    through `load_settings()`'s primary database, matching the API's
    `require_permission` -- so tests must set `ORCHAI_DATABASE_URL` (and
    `ORCHAI_AUTH_SECRET_KEY`) before calling this.
    """

    identity_runtime = build_identity_runtime_from_settings(load_settings())
    asyncio.run(
        identity_runtime.identity_service.create_user(
            CreateUserCommand(
                username=username,
                plain_password=password,
                is_superuser=is_superuser,
            )
        )
    )


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
    # PLAN is a gated stage like any other: local-flow stops at PLANNED after
    # the first gated stage runs, it never jumps ahead on its own.
    assert "task_state=PLANNED" in result.output
    assert "execution_state=COMPLETED" in result.output
    assert "suggestion_status=ACCEPTED" in result.output
    assert "suggested_role=TASK_PLANNER" in result.output
    assert "suggested_action=PLAN" in result.output
    assert "audit_records=" in result.output
    assert f"database={database_url}" in result.output

    task_id = _output_value(result.output, "task_id")
    project_id = _output_value(result.output, "project_id")
    authorization_id = _output_value(result.output, "authorization_id")
    execution_id = _output_value(result.output, "execution_id")

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
    filtered_audit_result = runner.invoke(
        app,
        [
            "audit",
            "list",
            "--database-url",
            database_url,
            "--execution-id",
            execution_id,
            "--authorization-id",
            authorization_id,
            "--limit",
            "10",
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
    filtered_events_result = runner.invoke(
        app,
        [
            "events",
            "list",
            "--database-url",
            database_url,
            "--execution-id",
            execution_id,
            "--event-type",
            "EXECUTION_COMPLETED",
            "--limit",
            "10",
        ],
    )
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
    filtered_metrics_result = runner.invoke(
        app,
        [
            "metrics",
            "list",
            "--database-url",
            database_url,
            "--execution-id",
            execution_id,
            "--name",
            "execution.success",
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
    tasks_result = runner.invoke(
        app,
        [
            "tasks",
            "list",
            "--database-url",
            database_url,
        ],
    )
    task_show_result = runner.invoke(
        app,
        [
            "tasks",
            "show",
            task_id,
            "--database-url",
            database_url,
        ],
    )
    authorizations_result = runner.invoke(
        app,
        [
            "authorizations",
            "list",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--limit",
            "5",
        ],
    )
    authorization_show_result = runner.invoke(
        app,
        [
            "authorizations",
            "show",
            authorization_id,
            "--database-url",
            database_url,
        ],
    )
    authorization_request_result = runner.invoke(
        app,
        [
            "authorizations",
            "request",
            task_id,
            "--database-url",
            database_url,
            "--role",
            "QUALITY_AGENT",
            "--action",
            "REVIEW",
            "--reason",
            "Need explicit review authorization",
            "--requester",
            "cli-test",
            "--execution-mode",
            "SUGGESTED",
            "--context-scope",
            "docs/INDEX.md",
            "--proposed-state",
            "REVIEWING",
        ],
    )
    requested_authorization_id = _output_value(
        authorization_request_result.output,
        "authorization_id",
    )
    authorization_decide_result = runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            requested_authorization_id,
            "--database-url",
            database_url,
            "--status",
            "REJECTED",
            "--decided-by",
            "review-manager",
            "--reason",
            "Review deferred",
        ],
    )
    executions_result = runner.invoke(
        app,
        [
            "executions",
            "list",
            "--database-url",
            database_url,
        ],
    )
    execution_show_result = runner.invoke(
        app,
        [
            "executions",
            "show",
            execution_id,
            "--database-url",
            database_url,
        ],
    )
    execution_context_result = runner.invoke(
        app,
        [
            "executions",
            "context",
            execution_id,
            "--database-url",
            database_url,
        ],
    )

    assert audit_result.exit_code == 0
    assert f"project_id={project_id}" in audit_result.output
    assert "operation=EXECUTION_COMPLETED" in audit_result.output
    assert filtered_audit_result.exit_code == 0
    assert f"execution_id={execution_id}" in filtered_audit_result.output
    assert f"authorization_id={authorization_id}" in filtered_audit_result.output
    assert events_result.exit_code == 0
    assert "event_type=EXECUTION_COMPLETED" in events_result.output
    assert filtered_events_result.exit_code == 0
    assert f"execution_id={execution_id}" in filtered_events_result.output
    assert "event_type=EXECUTION_COMPLETED" in filtered_events_result.output
    assert metrics_result.exit_code == 0
    assert "name=execution.success" in metrics_result.output
    assert filtered_metrics_result.exit_code == 0
    assert f"execution_id={execution_id}" in filtered_metrics_result.output
    assert "name=execution.success" in filtered_metrics_result.output
    assert suggestions_result.exit_code == 0
    assert "status=ACCEPTED" in suggestions_result.output
    assert tasks_result.exit_code == 0
    assert f"task_id={task_id}" in tasks_result.output
    assert task_show_result.exit_code == 0
    assert "state=PLANNED" in task_show_result.output
    assert "available_transitions=" in task_show_result.output
    assert "IMPLEMENTING" in task_show_result.output
    assert authorizations_result.exit_code == 0
    assert "status=GRANTED" in authorizations_result.output
    assert authorization_show_result.exit_code == 0
    assert "current_decision_status=GRANTED" in authorization_show_result.output
    assert authorization_request_result.exit_code == 0
    assert "status=" in authorization_request_result.output
    assert "role=QUALITY_AGENT" in authorization_request_result.output
    assert authorization_decide_result.exit_code == 0
    assert "status=REJECTED" in authorization_decide_result.output
    assert "current_decision_status=REJECTED" in authorization_decide_result.output
    assert executions_result.exit_code == 0
    assert f"execution_id={execution_id}" in executions_result.output
    assert execution_show_result.exit_code == 0
    assert "state=COMPLETED" in execution_show_result.output
    assert "available_transitions=" in execution_show_result.output
    assert execution_context_result.exit_code == 0
    assert "resource=docs/INDEX.md" in execution_context_result.output


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
    # PLAN is a gated stage like any other: without approval the task never
    # even reaches PLANNED, it stops at the PLANNING bookkeeping state.
    assert "task_state=PLANNING" in result.output
    assert "execution_id=" in result.output
    assert "suggested_role=TASK_PLANNER" in result.output
    assert "suggested_action=PLAN" in result.output
    assert "suggestion_status=PRESENTED" in result.output
    assert "blocked_reason=suggested_mode_requires_approval" in result.output


def test_cli_local_flow_manual_mode_advances_one_gated_stage_at_a_time(tmp_path) -> None:
    """MANUAL mode skips the *approval* step (an explicit command is enough),
    but it does not skip stages: it still advances exactly one stage per
    call, just like SUGGESTED and AUTOMATIC. A suggestion record is still
    generated and tracked (now ACCEPTED) for auditability — MANUAL mode is
    not suggestion-less, it is approval-less.
    """

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
    assert "task_state=PLANNED" in result.output
    assert "execution_state=COMPLETED" in result.output
    assert "suggested_role=TASK_PLANNER" in result.output
    assert "suggested_action=PLAN" in result.output
    assert "suggestion_status=ACCEPTED" in result.output
    assert "blocked_reason=" in result.output


def test_cli_local_flow_automatic_mode_blocks_plan_without_configured_policy(
    tmp_path,
) -> None:
    """AUTOMATIC mode may only skip the approval step for operations
    explicitly present in AutomaticExecutionPolicy.allowed_operations. The
    default policy only allows (DEVELOPER, IMPLEMENT), so a fresh
    AUTOMATIC-mode request — whose first gated stage is (TASK_PLANNER,
    PLAN) — is blocked exactly like SUGGESTED mode until that operation is
    explicitly configured. Nothing may jump stages "for free".
    """

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
    assert "task_state=PLANNING" in result.output
    assert "suggested_role=TASK_PLANNER" in result.output
    assert "suggested_action=PLAN" in result.output
    assert "suggestion_status=PRESENTED" in result.output
    assert "blocked_reason=automatic_policy_denied" in result.output


def test_cli_db_sync_prepares_sqlite_database(tmp_path) -> None:
    """'db sync' is the single, standard database administration command —
    'db create' and 'db migrate' no longer exist as separate commands. For a
    SQLite target, the create step is skipped (informational, not an error)
    and migrations are applied, which is what actually brings the database
    file into existence.
    """

    database_path = tmp_path / "orchai.db"
    database_url = f"sqlite:///{database_path}"
    runner = CliRunner()

    result = runner.invoke(app, ["db", "sync", "--database-url", database_url])

    assert result.exit_code == 0
    assert database_path.exists()
    assert "create_status=skipped_non_postgresql" in result.output
    assert "migrations=applied" in result.output
    assert "local-flow" in result.output


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


def test_cli_projects_register_persists_connected_project(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "projects",
            "register",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert f"name={tmp_path.name}" in result.output
    assert "observed_readiness_level=LEVEL_2_VALIDATABLE" in result.output

    list_result = runner.invoke(
        app,
        [
            "projects",
            "list",
            "--database-url",
            database_url,
        ],
    )

    assert list_result.exit_code == 0
    assert "projects=1" in list_result.output

    lookup_result = runner.invoke(
        app,
        [
            "projects",
            "lookup",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )
    other_project = tmp_path.parent / f"{tmp_path.name}-other"
    other_project.mkdir()
    missing_lookup_result = runner.invoke(
        app,
        [
            "projects",
            "lookup",
            str(other_project),
            "--database-url",
            database_url,
        ],
    )

    assert lookup_result.exit_code == 0
    assert "found=true" in lookup_result.output
    assert f"name={tmp_path.name}" in lookup_result.output
    assert missing_lookup_result.exit_code == 0
    assert "found=false" in missing_lookup_result.output


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


def test_cli_policies_evaluate_reports_allowed_and_blocked_cases(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    allowed_result = runner.invoke(
        app,
        [
            "policies",
            "evaluate",
            "--execution-mode",
            "MANUAL",
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--requested-model",
            "local-demo",
            "--effective-model",
            "local-demo",
            "--current-task-state",
            "PLANNED",
            "--project-operation",
            "WRITE_SOURCE",
            "--project-root",
            str(tmp_path),
            "--explicit-user-command",
            "--database-url",
            database_url,
        ],
    )
    blocked_result = runner.invoke(
        app,
        [
            "policies",
            "evaluate",
            "--execution-mode",
            "SUGGESTED",
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--requested-model",
            "local-demo",
            "--effective-model",
            "local-demo",
            "--current-task-state",
            "PLANNED",
            "--project-operation",
            "WRITE_SOURCE",
            "--project-root",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )

    assert allowed_result.exit_code == 0
    assert "allowed=true" in allowed_result.output
    assert "reason=manual_mode_direct_command" in allowed_result.output
    assert blocked_result.exit_code == 0
    assert "allowed=false" in blocked_result.output
    assert "reason=suggested_mode_requires_approval" in blocked_result.output


def test_cli_direct_task_and_execution_lifecycle_commands(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()
    project_register_result = runner.invoke(
        app,
        [
            "projects",
            "register",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )
    assert project_register_result.exit_code == 0
    project_id = _output_value(project_register_result.output, "project_id")

    task_create_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Direct lifecycle task",
            "--description",
            "Created through CLI",
            "--requested-change",
            "Implement CLI lifecycle coverage",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
            "--acceptance-criteria",
            "passes tests",
        ],
    )
    assert task_create_result.exit_code == 0
    task_id = _output_value(task_create_result.output, "task_id")
    assert "state=CREATED" in task_create_result.output
    assert "available_transitions=" in task_create_result.output
    assert "PLANNING" in task_create_result.output

    task_transition_result = runner.invoke(
        app,
        [
            "tasks",
            "transition",
            task_id,
            "--database-url",
            database_url,
            "--target-state",
            "PLANNING",
        ],
    )
    assert task_transition_result.exit_code == 0
    assert "state=PLANNING" in task_transition_result.output
    assert "available_transitions=" in task_transition_result.output
    assert "PLANNED" in task_transition_result.output

    authorization_request_result = runner.invoke(
        app,
        [
            "authorizations",
            "request",
            task_id,
            "--database-url",
            database_url,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--reason",
            "Need execution authorization",
            "--requester",
            "cli-test",
            "--execution-mode",
            "SUGGESTED",
            "--model-id",
            "local-demo",
            "--context-scope",
            "README.md",
        ],
    )
    assert authorization_request_result.exit_code == 0
    authorization_id = _output_value(
        authorization_request_result.output,
        "authorization_id",
    )

    authorization_decide_result = runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            authorization_id,
            "--database-url",
            database_url,
            "--status",
            "GRANTED",
            "--decided-by",
            "cli-manager",
            "--reason",
            "Approved",
        ],
    )
    assert authorization_decide_result.exit_code == 0
    assert "status=GRANTED" in authorization_decide_result.output

    execution_request_result = runner.invoke(
        app,
        [
            "executions",
            "request",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--model-id",
            "local-demo",
            "--authorization-id",
            authorization_id,
            "--project-id",
            project_id,
            "--requested-context",
            "README.md",
            "--authorized-context",
            "README.md",
        ],
    )
    assert execution_request_result.exit_code == 0
    execution_id = _output_value(execution_request_result.output, "execution_id")
    assert "state=AUTHORIZED" in execution_request_result.output
    assert "available_transitions=" in execution_request_result.output
    assert "PREPARING" in execution_request_result.output

    for target_state in ("PREPARING", "STARTED", "RUNNING"):
        transition_result = runner.invoke(
            app,
            [
                "executions",
                "transition",
                execution_id,
                "--database-url",
                database_url,
                "--target-state",
                target_state,
            ],
        )
        assert transition_result.exit_code == 0
        assert f"state={target_state}" in transition_result.output
        assert "available_transitions=" in transition_result.output

    complete_result = runner.invoke(
        app,
        [
            "executions",
            "complete",
            execution_id,
            "--database-url",
            database_url,
            "--output",
            "Implemented through direct lifecycle",
            "--success",
            "--warnings",
            "none",
            "--input-tokens",
            "10",
            "--output-tokens",
            "15",
            "--estimated-cost",
            "0.01",
        ],
    )
    assert complete_result.exit_code == 0
    assert "state=COMPLETED" in complete_result.output
    assert "result_success=true" in complete_result.output

    resolve_context_result = runner.invoke(
        app,
        [
            "executions",
            "resolve-context",
            execution_id,
            "--database-url",
            database_url,
            "--source",
            "SOURCE_FILE",
        ],
    )
    assert resolve_context_result.exit_code == 0
    assert "context_items=1" in resolve_context_result.output
    assert "resource=README.md" in resolve_context_result.output


def test_cli_executions_run_drives_execution_engine(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_register_result = runner.invoke(
        app,
        [
            "projects",
            "register",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )
    project_id = _output_value(project_register_result.output, "project_id")

    task_create_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Run execution task",
            "--description",
            "Drive execution engine through CLI",
            "--requested-change",
            "Run with stub provider",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
        ],
    )
    task_id = _output_value(task_create_result.output, "task_id")

    authorization_request_result = runner.invoke(
        app,
        [
            "authorizations",
            "request",
            task_id,
            "--database-url",
            database_url,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--reason",
            "Need execution authorization",
            "--requester",
            "cli-test",
            "--execution-mode",
            "SUGGESTED",
            "--model-id",
            "local-demo",
            "--context-scope",
            "README.md",
        ],
    )
    authorization_id = _output_value(
        authorization_request_result.output,
        "authorization_id",
    )
    runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            authorization_id,
            "--database-url",
            database_url,
            "--status",
            "GRANTED",
            "--decided-by",
            "cli-manager",
            "--reason",
            "Approved",
        ],
    )
    execution_request_result = runner.invoke(
        app,
        [
            "executions",
            "request",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--model-id",
            "local-demo",
            "--authorization-id",
            authorization_id,
            "--project-id",
            project_id,
            "--requested-context",
            "README.md",
            "--authorized-context",
            "README.md",
        ],
    )
    execution_id = _output_value(execution_request_result.output, "execution_id")

    run_result = runner.invoke(
        app,
        [
            "executions",
            "run",
            execution_id,
            "--database-url",
            database_url,
        ],
    )

    assert run_result.exit_code == 0
    assert "state=COMPLETED" in run_result.output
    assert "result_success=true" in run_result.output


def test_cli_executions_dispatch_schedules_async_execution(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_register_result = runner.invoke(
        app,
        [
            "projects",
            "register",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )
    project_id = _output_value(project_register_result.output, "project_id")

    task_create_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Dispatch execution task",
            "--description",
            "Drive async execution dispatch through CLI",
            "--requested-change",
            "Dispatch with stub provider",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
        ],
    )
    task_id = _output_value(task_create_result.output, "task_id")

    authorization_request_result = runner.invoke(
        app,
        [
            "authorizations",
            "request",
            task_id,
            "--database-url",
            database_url,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--reason",
            "Need execution authorization",
            "--requester",
            "cli-test",
            "--execution-mode",
            "SUGGESTED",
            "--model-id",
            "local-demo",
            "--context-scope",
            "README.md",
        ],
    )
    authorization_id = _output_value(
        authorization_request_result.output,
        "authorization_id",
    )
    runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            authorization_id,
            "--database-url",
            database_url,
            "--status",
            "GRANTED",
            "--decided-by",
            "cli-manager",
            "--reason",
            "Approved",
        ],
    )
    execution_request_result = runner.invoke(
        app,
        [
            "executions",
            "request",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--model-id",
            "local-demo",
            "--authorization-id",
            authorization_id,
            "--project-id",
            project_id,
            "--requested-context",
            "README.md",
            "--authorized-context",
            "README.md",
        ],
    )
    execution_id = _output_value(execution_request_result.output, "execution_id")

    dispatch_result = runner.invoke(
        app,
        [
            "executions",
            "dispatch",
            execution_id,
            "--database-url",
            database_url,
        ],
    )

    assert dispatch_result.exit_code == 0
    assert "dispatch_requested=true" in dispatch_result.output
    assert "dispatch_mode=synchronous_fallback" in dispatch_result.output
    assert "active_in_process=false" in dispatch_result.output
    assert "result_success=true" in dispatch_result.output

    final_show_result = runner.invoke(
        app,
        [
            "executions",
            "show",
            execution_id,
            "--database-url",
            database_url,
        ],
    )

    assert final_show_result.exit_code == 0
    assert "state=COMPLETED" in final_show_result.output


def test_cli_task_snapshot_returns_consolidated_operational_view(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_register_result = runner.invoke(
        app,
        [
            "projects",
            "register",
            str(tmp_path),
            "--database-url",
            database_url,
        ],
    )
    project_id = _output_value(project_register_result.output, "project_id")
    task_create_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Snapshot task",
            "--description",
            "Build task-centric snapshot",
            "--requested-change",
            "Aggregate one operational view",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
        ],
    )
    task_id = _output_value(task_create_result.output, "task_id")
    authorization_request_result = runner.invoke(
        app,
        [
            "authorizations",
            "request",
            task_id,
            "--database-url",
            database_url,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--reason",
            "Need execution authorization",
            "--requester",
            "cli-test",
            "--execution-mode",
            "SUGGESTED",
            "--model-id",
            "local-demo",
            "--context-scope",
            "README.md",
        ],
    )
    authorization_id = _output_value(
        authorization_request_result.output,
        "authorization_id",
    )
    runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            authorization_id,
            "--database-url",
            database_url,
            "--status",
            "GRANTED",
            "--decided-by",
            "cli-manager",
            "--reason",
            "Approved",
        ],
    )
    execution_request_result = runner.invoke(
        app,
        [
            "executions",
            "request",
            "--database-url",
            database_url,
            "--task-id",
            task_id,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--model-id",
            "local-demo",
            "--authorization-id",
            authorization_id,
            "--project-id",
            project_id,
            "--requested-context",
            "README.md",
            "--authorized-context",
            "README.md",
        ],
    )
    execution_id = _output_value(execution_request_result.output, "execution_id")
    runner.invoke(
        app,
        [
            "executions",
            "run",
            execution_id,
            "--database-url",
            database_url,
        ],
    )

    snapshot_result = runner.invoke(
        app,
        [
            "tasks",
            "snapshot",
            task_id,
            "--database-url",
            database_url,
            "--history-limit",
            "50",
        ],
    )

    assert snapshot_result.exit_code == 0
    assert f"task_id={task_id}" in snapshot_result.output
    assert "authorizations=1" in snapshot_result.output
    assert "executions=1" in snapshot_result.output
    assert "events=" in snapshot_result.output
    assert "audit_records=" in snapshot_result.output
    assert "metric_records=" in snapshot_result.output
    assert "context_records=" in snapshot_result.output
    assert f"authorization_id={authorization_id}" in snapshot_result.output
    assert f"execution_id={execution_id}" in snapshot_result.output
    assert "snapshot_authorization=true" in snapshot_result.output
    assert "snapshot_execution=true" in snapshot_result.output


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
    # The PLANNING->PLANNED bootstrap hop is gated exactly like the
    # operation itself: without approval the task doesn't even reach
    # PLANNED, so the operation never gets a chance to run.
    assert "task_state=PLANNING" in result.output
    assert "suggested_role=TASK_PLANNER" in result.output
    assert "suggested_action=PLAN" in result.output
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


def test_cli_projects_operate_automatic_mode_blocks_plan_without_configured_policy(
    tmp_path,
) -> None:
    """The CLI does not currently expose a way to configure
    AutomaticExecutionPolicy.allowed_operations, so an AUTOMATIC-mode
    project operation always hits the default policy — which does not
    include (TASK_PLANNER, PLAN) — and is blocked at the same PLAN
    bootstrap gate as SUGGESTED mode. See test_local_flow.py for proof that
    supplying that configuration through the Python API does let it
    through.
    """

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
    assert "task_state=PLANNING" in result.output
    assert "suggested_role=TASK_PLANNER" in result.output
    assert "suggested_action=PLAN" in result.output
    assert "blocked_reason=automatic_policy_denied" in result.output
    assert not (tmp_path / "src" / "automatic.py").exists()


def test_cli_projects_operate_accepts_cloud_provider_target(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()
    runner.invoke(
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
    runner.invoke(
        app,
        [
            "projects",
            "list",
            "--database-url",
            database_url,
        ],
    )
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
            "src/cloud.py",
            "--content",
            "print('cloud')",
            "--provider-target",
            "CLOUD",
            "--approve-operation",
        ],
    )

    assert result.exit_code == 0
    assert "blocked_reason=cloud_provider_sharing_requires_project_authorization" in result.output


def test_cli_local_flow_uses_configured_default_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ORCHAI_AI_MODEL", "configured-model")
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
            "--approve-suggestion",
        ],
    )

    assert result.exit_code == 0
    runtime = build_sqlalchemy_runtime(database_url)
    execution = runner.invoke(
        app,
        [
            "events",
            "list",
            "--database-url",
            database_url,
            "--task-id",
            _output_value(result.output, "task_id"),
            "--limit",
            "20",
        ],
    )
    assert execution.exit_code == 0
    persisted_execution = asyncio.run(
        runtime.execution_engine._execution_repository.get(
            ExecutionId(_output_value(result.output, "execution_id"))
        )
    )
    assert str(persisted_execution.model_id) == "configured-model"


def test_cli_db_sync_reports_sqlite_shorthand_alias_as_informational_not_error() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["db", "sync", "--database-url", "sqlite"])

    assert result.exit_code == 0
    assert "create_status=skipped_non_postgresql" in result.output
    assert "migrations=applied" in result.output
    assert "local-flow" in result.output


def test_cli_providers_show_reports_effective_settings(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_AI_PROVIDER", "ollama")
    monkeypatch.setenv("ORCHAI_AI_BASE_URL", "http://localhost:11434")
    runner = CliRunner()

    result = runner.invoke(app, ["providers", "show"])

    assert result.exit_code == 0
    assert "provider=ollama" in result.output
    assert "base_url=http://localhost:11434" in result.output


def test_cli_providers_capabilities_reports_declared_capabilities(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_AI_PROVIDER", "stub")
    runner = CliRunner()

    result = runner.invoke(app, ["providers", "capabilities"])

    assert result.exit_code == 0
    assert "provider=stub" in result.output
    assert "capabilities=execute,validate_request" in result.output


def test_cli_providers_health_reports_operational_status(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_AI_PROVIDER", "stub")
    runner = CliRunner()

    result = runner.invoke(app, ["providers", "health"])

    assert result.exit_code == 0
    assert "provider=stub" in result.output
    assert "reachable=true" in result.output


def test_cli_task_and_execution_lists_support_operational_filters(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_result = runner.invoke(
        app,
        ["projects", "register", str(tmp_path), "--database-url", database_url],
    )
    project_id = _output_value(project_result.output, "project_id")

    first_task_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--title",
            "First task",
            "--description",
            "Created through CLI",
            "--requested-change",
            "Implement first feature",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
            "--database-url",
            database_url,
        ],
    )
    second_task_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--title",
            "Second task",
            "--description",
            "Created through CLI",
            "--requested-change",
            "Implement second feature",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
            "--database-url",
            database_url,
        ],
    )
    first_task_id = _output_value(first_task_result.output, "task_id")
    second_task_id = _output_value(second_task_result.output, "task_id")

    runner.invoke(
        app,
        [
            "tasks",
            "transition",
            first_task_id,
            "--target-state",
            "PLANNING",
            "--database-url",
            database_url,
        ],
    )

    authorization_result = runner.invoke(
        app,
        [
            "authorizations",
            "request",
            first_task_id,
            "--database-url",
            database_url,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--reason",
            "Need execution authorization",
            "--requester",
            "cli-test",
            "--execution-mode",
            "SUGGESTED",
            "--model-id",
            "local-demo",
            "--context-scope",
            "README.md",
        ],
    )
    authorization_id = _output_value(authorization_result.output, "authorization_id")
    runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            authorization_id,
            "--database-url",
            database_url,
            "--status",
            "GRANTED",
            "--decided-by",
            "cli-manager",
            "--reason",
            "Approved",
        ],
    )
    execution_result = runner.invoke(
        app,
        [
            "executions",
            "request",
            "--task-id",
            first_task_id,
            "--role",
            "DEVELOPER",
            "--action",
            "IMPLEMENT",
            "--model-id",
            "local-demo",
            "--authorization-id",
            authorization_id,
            "--project-id",
            project_id,
            "--requested-context",
            "README.md",
            "--authorized-context",
            "README.md",
            "--database-url",
            database_url,
        ],
    )
    execution_id = _output_value(execution_result.output, "execution_id")
    runner.invoke(
        app,
        [
            "executions",
            "transition",
            execution_id,
            "--target-state",
            "PREPARING",
            "--database-url",
            database_url,
        ],
    )

    filtered_tasks_result = runner.invoke(
        app,
        [
            "tasks",
            "list",
            "--project-id",
            project_id,
            "--state",
            "PLANNING",
            "--limit",
            "5",
            "--database-url",
            database_url,
        ],
    )
    filtered_executions_result = runner.invoke(
        app,
        [
            "executions",
            "list",
            "--task-id",
            first_task_id,
            "--project-id",
            project_id,
            "--state",
            "PREPARING",
            "--limit",
            "5",
            "--database-url",
            database_url,
        ],
    )

    assert filtered_tasks_result.exit_code == 0
    assert "tasks=1" in filtered_tasks_result.output
    assert f"task_id={first_task_id}" in filtered_tasks_result.output
    assert f"task_id={second_task_id}" not in filtered_tasks_result.output
    assert "state=PLANNING" in filtered_tasks_result.output
    assert filtered_executions_result.exit_code == 0
    assert "executions=1" in filtered_executions_result.output
    assert f"execution_id={execution_id}" in filtered_executions_result.output
    assert "state=PREPARING" in filtered_executions_result.output


def test_cli_runtime_check_reports_consolidated_operational_status(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["runtime", "check", "--database-url", database_url],
    )

    assert result.exit_code == 0
    assert "ready=true" in result.output
    assert "operational_mode=local-only" in result.output
    assert f"database={database_url}" in result.output
    assert "database_reachable=true" in result.output
    assert "provider=stub" in result.output
    assert "provider_reachable=true" in result.output
    assert "warnings=1" in result.output


def test_cli_api_serve_uses_effective_host_and_port(monkeypatch) -> None:
    monkeypatch.setenv("ORCHAI_API_HOST", "0.0.0.0")
    monkeypatch.setenv("ORCHAI_API_PORT", "9000")
    calls: dict[str, object] = {}

    def fake_run(application, *, host, port) -> None:
        calls["application"] = application
        calls["host"] = host
        calls["port"] = port

    monkeypatch.setattr("orchai.interfaces.cli.main.uvicorn.run", fake_run)
    runner = CliRunner()

    result = runner.invoke(app, ["api", "serve"])

    assert result.exit_code == 0
    assert "host=0.0.0.0" in result.output
    assert "port=9000" in result.output
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9000


def test_cli_tasks_advance_runs_task_centric_workflow_to_documentation(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    (tests_dir / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_result = runner.invoke(
        app,
        ["projects", "register", str(tmp_path), "--database-url", database_url],
    )
    project_id = _output_value(project_result.output, "project_id")
    task_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--title",
            "Workflow task",
            "--description",
            "Advance through staged orchestration",
            "--requested-change",
            "Plan, implement, validate, test, and document",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
            "--database-url",
            database_url,
        ],
    )
    task_id = _output_value(task_result.output, "task_id")

    for expected_stage, expected_state in (
        ("PLAN", "PLANNED"),
        ("IMPLEMENT", "IMPLEMENTED"),
        ("REVIEW", "REVIEWING"),
        ("VALIDATE", "VALIDATING"),
    ):
        result = runner.invoke(
            app,
            [
                "tasks",
                "advance",
                task_id,
                "--context-path",
                "docs/INDEX.md",
                "--approve-stage",
                "--database-url",
                database_url,
            ],
        )
        assert result.exit_code == 0
        assert f"stage={expected_stage}" in result.output
        assert f"task_state={expected_state}" in result.output
        assert "execution_state=COMPLETED" in result.output
        assert "blocked_reason=" in result.output

    test_result = runner.invoke(
        app,
        [
            "tasks",
            "advance",
            task_id,
            "--stage",
            "TEST",
            "--approve-stage",
            "--database-url",
            database_url,
        ],
    )
    assert test_result.exit_code == 0
    assert "stage=TEST" in test_result.output
    assert "task_state=VALIDATED" in test_result.output

    document_result = runner.invoke(
        app,
        [
            "tasks",
            "advance",
            task_id,
            "--stage",
            "DOCUMENT",
            "--context-path",
            "docs/INDEX.md",
            "--documentation-path",
            "docs/RESULT.md",
            "--approve-stage",
            "--database-url",
            database_url,
        ],
    )
    assert document_result.exit_code == 0
    assert "stage=DOCUMENT" in document_result.output
    assert "task_state=COMPLETED" in document_result.output
    assert "resource=docs/RESULT.md" in document_result.output
    assert "execution_state=COMPLETED" in document_result.output
    assert "Stub provider processed" in (docs / "RESULT.md").read_text(encoding="utf-8")


def test_cli_authorizations_list_supports_status_and_pending_only_filters(
    tmp_path,
) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_result = runner.invoke(
        app,
        ["projects", "register", str(tmp_path), "--database-url", database_url],
    )
    assert project_result.exit_code == 0
    project_id = _output_value(project_result.output, "project_id")

    task_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Authorization filter task",
            "--description",
            "Covers authorizations list filters",
            "--requested-change",
            "Implement a change",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
        ],
    )
    assert task_result.exit_code == 0
    task_id = _output_value(task_result.output, "task_id")

    def _request_authorization() -> str:
        result = runner.invoke(
            app,
            [
                "authorizations",
                "request",
                task_id,
                "--database-url",
                database_url,
                "--role",
                "DEVELOPER",
                "--action",
                "IMPLEMENT",
                "--reason",
                "Need execution authorization",
                "--requester",
                "cli-filter-test",
                "--execution-mode",
                "SUGGESTED",
                "--model-id",
                "local-demo",
            ],
        )
        assert result.exit_code == 0
        return _output_value(result.output, "authorization_id")

    granted_id = _request_authorization()
    pending_id = _request_authorization()

    decide_result = runner.invoke(
        app,
        [
            "authorizations",
            "decide",
            granted_id,
            "--database-url",
            database_url,
            "--status",
            "GRANTED",
            "--decided-by",
            "cli-filter-test",
            "--reason",
            "Approved",
        ],
    )
    assert decide_result.exit_code == 0

    all_result = runner.invoke(
        app,
        [
            "authorizations",
            "list",
            "--task-id",
            task_id,
            "--database-url",
            database_url,
        ],
    )
    assert all_result.exit_code == 0
    assert "authorizations=2" in all_result.output

    pending_result = runner.invoke(
        app,
        [
            "authorizations",
            "list",
            "--task-id",
            task_id,
            "--pending-only",
            "--database-url",
            database_url,
        ],
    )
    assert pending_result.exit_code == 0
    assert "authorizations=1" in pending_result.output
    assert f"authorization_id={pending_id}" in pending_result.output
    assert f"authorization_id={granted_id}" not in pending_result.output

    granted_result = runner.invoke(
        app,
        [
            "authorizations",
            "list",
            "--task-id",
            task_id,
            "--status",
            "GRANTED",
            "--database-url",
            database_url,
        ],
    )
    assert granted_result.exit_code == 0
    assert "authorizations=1" in granted_result.output
    assert f"authorization_id={granted_id}" in granted_result.output
    assert f"authorization_id={pending_id}" not in granted_result.output


def test_cli_audit_show_returns_matching_record(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_result = runner.invoke(
        app,
        ["projects", "register", str(tmp_path), "--database-url", database_url],
    )
    assert project_result.exit_code == 0
    project_id = _output_value(project_result.output, "project_id")

    task_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Audit show task",
            "--description",
            "Covers audit show command",
            "--requested-change",
            "Implement a change",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
        ],
    )
    assert task_result.exit_code == 0
    task_id = _output_value(task_result.output, "task_id")

    list_result = runner.invoke(
        app,
        ["audit", "list", "--task-id", task_id, "--database-url", database_url],
    )
    assert list_result.exit_code == 0
    # `audit list` prints one audit record per line with all fields
    # space-joined (e.g. "audit_id=... occurred_at=... ..."), unlike the
    # one-key-per-line format `_output_value` expects, so extract just the
    # first token instead of using that helper here.
    first_record_line = next(
        line for line in list_result.output.splitlines() if line.startswith("audit_id=")
    )
    audit_id = first_record_line.split(" ", 1)[0].removeprefix("audit_id=")

    show_result = runner.invoke(
        app,
        ["audit", "show", audit_id, "--database-url", database_url],
    )
    assert show_result.exit_code == 0
    assert f"audit_id={audit_id}" in show_result.output
    assert f"task_id={task_id}" in show_result.output


def test_cli_suggestions_show_generate_accept_reject_commands(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    project_result = runner.invoke(
        app,
        ["projects", "register", str(tmp_path), "--database-url", database_url],
    )
    assert project_result.exit_code == 0
    project_id = _output_value(project_result.output, "project_id")

    task_result = runner.invoke(
        app,
        [
            "tasks",
            "create",
            "--database-url",
            database_url,
            "--title",
            "Suggestion lifecycle task",
            "--description",
            "Covers suggestion generate/show/accept/reject",
            "--requested-change",
            "Implement a change",
            "--project-id",
            project_id,
            "--execution-mode",
            "SUGGESTED",
        ],
    )
    assert task_result.exit_code == 0
    task_id = _output_value(task_result.output, "task_id")

    transition_result = runner.invoke(
        app,
        [
            "tasks",
            "transition",
            task_id,
            "--database-url",
            database_url,
            "--target-state",
            "PLANNING",
        ],
    )
    assert transition_result.exit_code == 0

    generate_result = runner.invoke(
        app,
        ["suggestions", "generate", task_id, "--database-url", database_url],
    )
    assert generate_result.exit_code == 0
    assert "status=GENERATED" in generate_result.output
    suggestion_id = _output_value(generate_result.output, "suggestion_id")

    show_result = runner.invoke(
        app,
        ["suggestions", "show", suggestion_id, "--database-url", database_url],
    )
    assert show_result.exit_code == 0
    assert f"suggestion_id={suggestion_id}" in show_result.output

    accept_result = runner.invoke(
        app,
        ["suggestions", "accept", suggestion_id, "--database-url", database_url],
    )
    assert accept_result.exit_code == 0
    assert "status=ACCEPTED" in accept_result.output

    reject_result = runner.invoke(
        app,
        ["suggestions", "reject", suggestion_id, "--database-url", database_url],
    )
    assert reject_result.exit_code == 0
    assert "status=REJECTED" in reject_result.output


def test_cli_auth_bootstrap_admin_login_logout_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    credentials_path = tmp_path / ".orchai" / "credentials.json"
    runner = CliRunner()

    bootstrap_result = runner.invoke(
        app,
        [
            "auth",
            "bootstrap-admin",
            "--username",
            "admin",
            "--password",
            "correct horse battery",
        ],
    )
    assert bootstrap_result.exit_code == 0
    assert "Created superuser 'admin'." in bootstrap_result.output

    second_bootstrap_result = runner.invoke(
        app,
        [
            "auth",
            "bootstrap-admin",
            "--username",
            "someone-else",
            "--password",
            "correct horse battery",
        ],
    )
    assert second_bootstrap_result.exit_code == 1
    assert "already present" in second_bootstrap_result.output

    login_result = runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "admin",
            "--password",
            "correct horse battery",
        ],
    )
    assert login_result.exit_code == 0
    assert "Logged in as admin." in login_result.output
    assert credentials_path.exists()

    logout_result = runner.invoke(app, ["auth", "logout"])
    assert logout_result.exit_code == 0
    assert "Logged out." in logout_result.output
    assert not credentials_path.exists()


def test_cli_unenforced_by_default_allows_commands_without_login(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("ORCHAI_AUTH_ENFORCED", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    runner = CliRunner()

    result = runner.invoke(app, ["db", "sync", "--database-url", database_url])

    assert result.exit_code == 0


def test_cli_enforced_requires_authentication(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    identity_database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", identity_database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="admin", password="correct horse battery", is_superuser=True)
    runner = CliRunner()

    unauthenticated_result = runner.invoke(
        app, ["db", "sync", "--database-url", identity_database_url]
    )
    assert unauthenticated_result.exit_code == 1
    assert "not authenticated" in unauthenticated_result.output

    login_result = runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "admin",
            "--password",
            "correct horse battery",
        ],
    )
    assert login_result.exit_code == 0

    authenticated_result = runner.invoke(
        app, ["db", "sync", "--database-url", identity_database_url]
    )
    assert authenticated_result.exit_code == 0
    assert "migrations=applied" in authenticated_result.output


def test_cli_enforced_rejects_a_user_missing_the_required_permission(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(
        username="scoped", password="correct horse battery", is_superuser=False
    )
    runner = CliRunner()

    login_result = runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "scoped",
            "--password",
            "correct horse battery",
        ],
    )
    assert login_result.exit_code == 0

    # 'tasks list' requires "projects:read", which "scoped" was never granted.
    denied_result = runner.invoke(
        app, ["tasks", "list", "--database-url", database_url]
    )
    assert denied_result.exit_code == 1
    assert "missing required permission: projects:read" in denied_result.output

    # 'projects discover' only requires authentication, no specific
    # permission, so the same unprivileged user succeeds.
    (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
    allowed_result = runner.invoke(app, ["projects", "discover", str(tmp_path)])
    assert allowed_result.exit_code == 0
    assert "adapter_type=local_filesystem" in allowed_result.output


def test_cli_enforced_orchai_token_env_var_is_honored(monkeypatch, tmp_path) -> None:
    """`ORCHAI_TOKEN` is checked before the local credentials file (per
    `require_cli_permission`'s resolution order), which matters for
    non-interactive/CI use where no `auth login` has run in this
    environment."""

    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="admin", password="correct horse battery", is_superuser=True)
    runner = CliRunner()

    login_result = runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "admin",
            "--password",
            "correct horse battery",
        ],
    )
    assert login_result.exit_code == 0
    credentials_path = tmp_path / ".orchai" / "credentials.json"
    access_token = json.loads(credentials_path.read_text(encoding="utf-8"))[
        "access_token"
    ]
    credentials_path.unlink()

    monkeypatch.setenv("ORCHAI_TOKEN", access_token)
    result = runner.invoke(app, ["db", "sync", "--database-url", database_url])

    assert result.exit_code == 0
    assert "migrations=applied" in result.output


# ---------------------------------------------------------------------------
# User-configuration CRUD (admin + self-service, ADR-012)
# ---------------------------------------------------------------------------


def _permission_id(key: str) -> str:
    """Resolve a permission id from the auto-seeded catalog, by key.

    There is no `orchai permissions ...` command (permissions are a fixed
    system catalog, not admin-creatable), so tests reach the identity
    service directly, exactly like `_create_user` does for setup.
    """

    identity_runtime = build_identity_runtime_from_settings(load_settings())
    permissions = asyncio.run(identity_runtime.identity_service.list_permissions(limit=100))
    return str(next(p.id for p in permissions if p.key == key))


def test_cli_admin_users_and_access_roles_crud_flow(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    runner = CliRunner()

    login_result = runner.invoke(
        app,
        ["auth", "login", "--username", "root", "--password", "correct horse battery"],
    )
    assert login_result.exit_code == 0

    create_role_result = runner.invoke(
        app, ["access-roles", "create", "--name", "Engineer"]
    )
    assert create_role_result.exit_code == 0
    role_id = _output_value(create_role_result.output, "role_id")

    duplicate_role_result = runner.invoke(
        app, ["access-roles", "create", "--name", "Engineer"]
    )
    assert duplicate_role_result.exit_code == 1
    assert "already taken" in duplicate_role_result.output

    set_permissions_result = runner.invoke(
        app,
        [
            "access-roles",
            "set-permissions",
            role_id,
            "--permission-id",
            _permission_id("projects:read"),
            "--permission-id",
            _permission_id("requests:create"),
        ],
    )
    assert set_permissions_result.exit_code == 0
    assert set(_output_value(set_permissions_result.output, "permissions").split(",")) == {
        "projects:read",
        "requests:create",
    }

    no_role_result = runner.invoke(
        app,
        [
            "users",
            "create",
            "--username",
            "norole",
            "--password",
            "correct horse battery",
        ],
    )
    assert no_role_result.exit_code == 1
    assert "at least one access role" in no_role_result.output

    create_user_result = runner.invoke(
        app,
        [
            "users",
            "create",
            "--username",
            "alice",
            "--password",
            "correct horse battery",
            "--role-id",
            role_id,
        ],
    )
    assert create_user_result.exit_code == 0
    alice_id = _output_value(create_user_result.output, "user_id")
    assert _output_value(create_user_result.output, "access_roles") == "Engineer"

    list_users_result = runner.invoke(app, ["users", "list"])
    assert list_users_result.exit_code == 0
    assert "username=alice" in list_users_result.output
    assert "username=root" in list_users_result.output

    list_roles_result = runner.invoke(app, ["access-roles", "list"])
    assert list_roles_result.exit_code == 0
    assert f"role_id={role_id}" in list_roles_result.output
    assert "users=alice" in list_roles_result.output

    empty_roles_result = runner.invoke(
        app, ["users", "set-access-roles", alice_id]
    )
    assert empty_roles_result.exit_code == 1
    assert "at least one access role" in empty_roles_result.output

    second_role_id = _output_value(
        runner.invoke(app, ["access-roles", "create", "--name", "Reviewer"]).output,
        "role_id",
    )
    replace_roles_result = runner.invoke(
        app, ["users", "set-access-roles", alice_id, "--role-id", second_role_id]
    )
    assert replace_roles_result.exit_code == 0
    assert _output_value(replace_roles_result.output, "access_roles") == "Reviewer"

    # A non-admin user is rejected from every admin command.
    credentials_path = tmp_path / ".orchai" / "credentials.json"
    credentials_path.unlink()
    runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "alice",
            "--password",
            "correct horse battery",
        ],
    )
    denied_result = runner.invoke(app, ["users", "list"])
    assert denied_result.exit_code == 1
    assert "missing required permission: admin:manage_users" in denied_result.output


def test_cli_me_show_update_and_projects(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    runner = CliRunner()
    runner.invoke(
        app,
        ["auth", "login", "--username", "root", "--password", "correct horse battery"],
    )
    role_id = _output_value(
        runner.invoke(app, ["access-roles", "create", "--name", "Basic"]).output,
        "role_id",
    )
    runner.invoke(
        app,
        [
            "users",
            "create",
            "--username",
            "alice",
            "--password",
            "correct horse battery",
            "--role-id",
            role_id,
        ],
    )
    (tmp_path / ".orchai" / "credentials.json").unlink()
    runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "alice",
            "--password",
            "correct horse battery",
        ],
    )

    show_result = runner.invoke(app, ["me", "show"])
    assert show_result.exit_code == 0
    assert _output_value(show_result.output, "username") == "alice"
    assert _output_value(show_result.output, "access_roles") == "Basic"

    update_result = runner.invoke(
        app, ["me", "update", "--email", "alice@example.com"]
    )
    assert update_result.exit_code == 0
    assert _output_value(update_result.output, "email") == "alice@example.com"

    duplicate_username_result = runner.invoke(
        app, ["me", "update", "--username", "root"]
    )
    assert duplicate_username_result.exit_code == 1
    assert "already taken" in duplicate_username_result.output

    projects_result = runner.invoke(app, ["me", "projects"])
    assert projects_result.exit_code == 0
    assert "projects=0" in projects_result.output


def test_cli_projects_list_all_requires_admin_manage_projects(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    _create_user(
        username="scoped", password="correct horse battery", is_superuser=False
    )
    runner = CliRunner()

    runner.invoke(
        app,
        [
            "auth",
            "login",
            "--username",
            "scoped",
            "--password",
            "correct horse battery",
        ],
    )
    denied_result = runner.invoke(
        app, ["projects", "list-all", "--database-url", database_url]
    )
    assert denied_result.exit_code == 1
    assert "missing required permission: admin:manage_projects" in denied_result.output

    (tmp_path / ".orchai" / "credentials.json").unlink()
    runner.invoke(
        app,
        ["auth", "login", "--username", "root", "--password", "correct horse battery"],
    )
    allowed_result = runner.invoke(
        app, ["projects", "list-all", "--database-url", database_url]
    )
    assert allowed_result.exit_code == 0
    assert "projects=0" in allowed_result.output


def _output_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"missing output key: {key}")
