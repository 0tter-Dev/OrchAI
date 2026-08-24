import asyncio

from orchai.application.orchestration import (
    AutomaticExecutionPolicy,
    run_local_flow,
    run_project_operation,
    run_task_workflow_stage,
)
from orchai.bootstrap import (
    build_sqlalchemy_local_flow_dependencies,
    build_sqlalchemy_runtime,
)
from orchai.domain.actions import ActionName
from orchai.domain.identifiers import ExecutionId, TaskId
from orchai.domain.projects import ProjectOperation
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import SuggestionStatus
from orchai.domain.tasks import ExecutionMode
from orchai.infrastructure.persistence import SQLAlchemyProjectRepository


def test_local_flow_stops_at_planned_pending_the_next_gated_stage(tmp_path) -> None:
    """POST /flows/local (like /requests) never advances past a gate on its own.

    Per docs/architecture/CHAT-FIRST-REQUEST-MODEL.md section 3 and ADR-011
    invariant #2, PLAN is a stage like any other: run_local_flow only creates
    the project/task and advances through the first gated stage (PLAN). It
    must not silently reach IMPLEMENTED in one call — that requires a second,
    explicit advance through the IMPLEMENT stage, exactly like every other
    stage transition.
    """

    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"

        result = await run_local_flow(
            project_root=tmp_path,
            context_path="docs/INDEX.md",
            title="Integration flow",
            model="local-demo",
            dependencies=build_sqlalchemy_local_flow_dependencies(database_url),
            storage_label=database_url,
            approve_suggestion=True,
        )

        # The PLAN stage itself ran for real (authorized + executed), but the
        # task stops at PLANNED — it does not jump ahead to IMPLEMENTED.
        assert result["task_state"] == "PLANNED"
        assert result["execution_state"] == "COMPLETED"
        assert result["suggestion_status"] == "ACCEPTED"
        assert result["suggested_role"] == "TASK_PLANNER"
        assert result["suggested_action"] == "PLAN"
        assert result["context_items"] == "1"
        assert result["database"].startswith("sqlite:///")
        assert int(result["events"]) >= 5
        assert int(result["audit_records"]) >= 5

        # Advancing to IMPLEMENT requires its own explicit, gated call.
        implement_result = await run_task_workflow_stage(
            task_id=result["task_id"],
            dependencies=build_sqlalchemy_local_flow_dependencies(database_url),
            storage_label=database_url,
            model="local-demo",
            context_paths=("docs/INDEX.md",),
            approve_stage=True,
        )
        assert implement_result["task_state"] == "IMPLEMENTED"
        assert implement_result["execution_state"] == "COMPLETED"
        assert implement_result["suggested_action"] == "IMPLEMENT"

        restarted_runtime = build_sqlalchemy_runtime(database_url)
        task_id = TaskId(result["task_id"])
        persisted_events = await restarted_runtime.event_repository.list(
            task_id=task_id,
            limit=100,
        )
        persisted_audit_records = await restarted_runtime.audit_repository.list(
            task_id=task_id,
            limit=100,
        )
        persisted_context_records = (
            await restarted_runtime.context_resolution_repository.list_by_execution(
                ExecutionId(implement_result["execution_id"])
            )
        )
        persisted_metrics = await restarted_runtime.metrics_repository.list(
            task_id=task_id,
            limit=100,
        )
        persisted_suggestions = await restarted_runtime.suggestion_repository.list(
            task_id=task_id,
            limit=100,
        )

        assert len(persisted_events) >= 10
        assert len(persisted_audit_records) >= 10
        assert len(persisted_context_records) == 1
        assert {record.name for record in persisted_metrics} >= {
            "execution.success",
            "execution.duration",
        }
        assert len({record.id for record in persisted_metrics}) == len(persisted_metrics)
        assert {s.status for s in persisted_suggestions} == {SuggestionStatus.ACCEPTED}
        assert persisted_context_records[0].reference.resource == "docs/INDEX.md"
        assert persisted_audit_records[0].task_id == task_id
        assert restarted_runtime.database is not None
        project = await SQLAlchemyProjectRepository(restarted_runtime.database).get(
            result["project_id"]
        )
        assert project.readiness_level.value == "LEVEL_2_VALIDATABLE"
        assert project.security_profile.metadata["has_git"] == "True"

    asyncio.run(run())


def test_local_flow_automatic_mode_only_skips_approval_with_prior_configuration(
    tmp_path,
) -> None:
    """AUTOMATIC mode never jumps a stage "for free" — it only proceeds
    without a human decision when the (role, action) pair is explicitly
    present in AutomaticExecutionPolicy.allowed_operations. The default
    policy denies (TASK_PLANNER, PLAN); configuring it in explicitly is the
    only way an AUTOMATIC-mode request advances past the PLAN stage on its
    own, mirroring the same rule enforced for every other stage.
    """

    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"

        default_policy_result = await run_local_flow(
            project_root=tmp_path,
            context_path="docs/INDEX.md",
            title="Automatic without configuration",
            model="local-demo",
            dependencies=build_sqlalchemy_local_flow_dependencies(database_url),
            storage_label=database_url,
            execution_mode=ExecutionMode.AUTOMATIC,
        )
        assert default_policy_result["task_state"] == "PLANNING"
        assert default_policy_result["blocked_reason"] == "automatic_policy_denied"

        configured_policy_result = await run_local_flow(
            project_root=tmp_path,
            context_path="docs/INDEX.md",
            title="Automatic with PLAN explicitly configured",
            model="local-demo",
            dependencies=build_sqlalchemy_local_flow_dependencies(database_url),
            storage_label=database_url,
            execution_mode=ExecutionMode.AUTOMATIC,
            automatic_policy=AutomaticExecutionPolicy(
                allowed_operations=(
                    (RoleName.TASK_PLANNER, ActionName.PLAN),
                    (RoleName.DEVELOPER, ActionName.IMPLEMENT),
                ),
            ),
        )
        assert configured_policy_result["task_state"] == "PLANNED"
        assert configured_policy_result["execution_state"] == "COMPLETED"
        assert configured_policy_result["suggestion_status"] == "ACCEPTED"
        assert configured_policy_result["blocked_reason"] == ""

    asyncio.run(run())


def test_project_operation_automatic_mode_only_skips_approval_with_prior_configuration(
    tmp_path,
) -> None:
    """The same non-bypass rule applies to POST /projects/operations: the
    task it creates must reach PLANNED (a state-machine prerequisite) before
    its own operation runs, and that bootstrap hop is gated identically to
    any other stage. AUTOMATIC mode only skips it once (TASK_PLANNER, PLAN)
    is explicitly configured.
    """

    async def run() -> None:
        (tmp_path / ".git").mkdir()
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"

        default_policy_result = await run_project_operation(
            project_root=tmp_path,
            operation=ProjectOperation.WRITE_SOURCE,
            title="Automatic operation without configuration",
            dependencies=build_sqlalchemy_local_flow_dependencies(database_url),
            storage_label=database_url,
            resource="src/automatic.py",
            content="print('automatic')",
            execution_mode=ExecutionMode.AUTOMATIC,
        )
        assert default_policy_result["task_state"] == "PLANNING"
        assert default_policy_result["blocked_reason"] == "automatic_policy_denied"
        assert not (tmp_path / "src" / "automatic.py").exists()

        configured_policy_result = await run_project_operation(
            project_root=tmp_path,
            operation=ProjectOperation.WRITE_SOURCE,
            title="Automatic operation with PLAN explicitly configured",
            dependencies=build_sqlalchemy_local_flow_dependencies(database_url),
            storage_label=database_url,
            resource="src/automatic.py",
            content="print('automatic')",
            execution_mode=ExecutionMode.AUTOMATIC,
            automatic_policy=AutomaticExecutionPolicy(
                allowed_operations=(
                    (RoleName.TASK_PLANNER, ActionName.PLAN),
                    (RoleName.DEVELOPER, ActionName.IMPLEMENT),
                ),
            ),
        )
        assert configured_policy_result["task_state"] == "IMPLEMENTED"
        assert configured_policy_result["blocked_reason"] == ""
        assert (
            tmp_path / "src" / "automatic.py"
        ).read_text(encoding="utf-8") == "print('automatic')"

    asyncio.run(run())
