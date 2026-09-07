import asyncio
import json
import time

from fastapi.testclient import TestClient

from orchai.application.identity import CreateUserCommand
from orchai.bootstrap import build_identity_runtime_from_settings
from orchai.infrastructure.configuration import load_settings
from orchai.interfaces.api import app

_TEST_SECRET_KEY = "api-test-secret-key-with-at-least-32-characters"


def _collect_sse_events(client: TestClient, path: str, *, json_body: dict) -> list[dict]:
    """Post to an SSE endpoint and return every `data:` payload, parsed."""

    events = []
    with client.stream("POST", path, json=json_body) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


def _create_user(*, username: str, password: str, is_superuser: bool) -> None:
    """Create a user directly in the identity DB the API/CLI will read.

    `/auth/*` and `require_permission` always resolve identity through
    `load_settings()`'s primary database -- never a per-request
    `database_url` override (a deliberate security decision, see
    `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`) -- so tests must set
    `ORCHAI_DATABASE_URL` before calling this, matching what the running
    app will see.
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


def test_api_root_index_and_provider_settings_endpoints() -> None:
    client = TestClient(app)

    root_response = client.get("/")
    assert root_response.status_code == 200
    root_payload = root_response.json()
    assert root_payload["service"] == "OrchAI API"
    assert root_payload["recommended_operational_dialect"] == "postgresql"
    assert root_payload["entry_points"]["provider_settings"] == "/providers/settings"
    assert root_payload["docs_url"] == "/docs"
    assert root_payload["openapi_url"] == "/openapi.json"

    provider_settings_response = client.get("/providers/settings")
    assert provider_settings_response.status_code == 200
    provider_payload = provider_settings_response.json()
    assert provider_payload["provider"] in {"stub", "litellm"}
    assert "api_key_configured" in provider_payload

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    openapi_payload = openapi_response.json()
    assert openapi_payload["info"]["title"] == "OrchAI API"
    assert "/providers/settings" in openapi_payload["paths"]


def test_api_modules_endpoints_list_and_show_forge_and_studio_without_system_prompt() -> None:
    client = TestClient(app)

    list_response = client.get("/modules")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 2
    by_id = {module["module_id"]: module for module in list_payload["modules"]}
    assert set(by_id) == {"forge", "studio"}

    forge = by_id["forge"]
    assert forge["name"] == "Forge"
    assert forge["requires_project"] is True
    assert forge["project_adapter_kind"] == "local_filesystem"
    assert forge["task_pipeline_mode"] == "full_workflow"
    assert "system_prompt" not in forge

    studio = by_id["studio"]
    assert studio["name"] == "Studio"
    assert studio["requires_project"] is True
    assert studio["project_adapter_kind"] == "media_workspace"
    assert studio["task_pipeline_mode"] == "conversational_with_protected_operations"
    assert studio["allowed_roles"] == ["TASK_PLANNER"]
    assert studio["allowed_actions"] == ["PLAN"]
    assert "system_prompt" not in studio

    show_response = client.get("/modules/forge")
    assert show_response.status_code == 200
    assert show_response.json() == forge

    missing_response = client.get("/modules/does-not-exist")
    assert missing_response.status_code == 404


def test_api_conversation_endpoints_persist_and_reply_to_messages(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    create_response = client.post(
        "/conversations",
        json={"module_id": "forge", "project_id": "proj-1", "database_url": database_url},
    )
    assert create_response.status_code == 200
    conversation = create_response.json()
    conversation_id = conversation["conversation_id"]
    assert conversation["module_id"] == "forge"
    assert conversation["archived"] is False

    events = _collect_sse_events(
        client,
        f"/conversations/{conversation_id}/messages",
        json_body={"content": "hello there", "database_url": database_url},
    )
    assert events[0]["type"] == "user_message"
    assert events[0]["message"]["role"] == "USER"
    assert events[0]["message"]["content"] == "hello there"
    assert [event["type"] for event in events[1:-1]] == ["delta"] * (len(events) - 2)
    assert events[-1]["type"] == "done"
    assert events[-1]["message"]["role"] == "ASSISTANT"
    assert events[-1]["message"]["status"] == "COMPLETE"
    assert events[-1]["message"]["provider_name"] == "stub"

    unknown_conversation_response = client.post(
        "/conversations/does-not-exist/messages",
        json={"content": "hi", "database_url": database_url},
    )
    assert unknown_conversation_response.status_code == 404

    messages_response = client.get(
        f"/conversations/{conversation_id}/messages",
        params={"database_url": database_url},
    )
    assert messages_response.status_code == 200
    assert messages_response.json()["count"] == 2

    list_response = client.get(
        "/conversations",
        params={"module_id": "forge", "database_url": database_url},
    )
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    missing_response = client.get(
        "/conversations/does-not-exist",
        params={"database_url": database_url},
    )
    assert missing_response.status_code == 404

    missing_module_response = client.post(
        "/conversations",
        json={"module_id": "does-not-exist", "database_url": database_url},
    )
    assert missing_module_response.status_code == 404

    studio_without_project_response = client.post(
        "/conversations",
        json={"module_id": "studio", "database_url": database_url},
    )
    assert studio_without_project_response.status_code == 400


def test_api_conversation_escalate_endpoint_creates_a_linked_task_via_requests(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Sample project", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    conversation_response = client.post(
        "/conversations",
        json={"module_id": "forge", "project_id": project_id, "database_url": database_url},
    )
    conversation_id = conversation_response.json()["conversation_id"]

    escalate_response = client.post(
        f"/conversations/{conversation_id}/escalate",
        json={
            "content": "Plan: review the README for accuracy",
            "context_paths": ["README.md"],
            "database_url": database_url,
        },
    )
    assert escalate_response.status_code == 200
    payload = escalate_response.json()
    assert payload["message"]["role"] == "USER"
    assert payload["message"]["content"] == "Plan: review the README for accuracy"
    task_id = payload["message"]["linked_task_id"]
    assert task_id
    assert payload["flow"]["status"] == "PENDING_SUGGESTION"
    assert payload["flow"]["task"]["state"] == "PLANNING"

    # The escalation is visible in the conversation transcript, and the
    # linked Task can be approved through the exact same /requests surface
    # any other caller uses -- escalation introduces no separate path.
    messages_response = client.get(
        f"/conversations/{conversation_id}/messages",
        params={"database_url": database_url},
    )
    assert messages_response.json()["messages"][0]["linked_task_id"] == task_id

    approve_response = client.post(
        f"/requests/{task_id}/approve",
        json={
            "reason": "looks fine",
            "context_paths": ["README.md"],
            "database_url": database_url,
        },
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approved"] is True
    assert approve_response.json()["task_state"] == "PLANNED"

    # Regression test for the stale-suggestion bug found while verifying
    # this exact flow (docs/TO-DO.md Priority 3.4): approving must not
    # leave the flow permanently reporting PENDING_SUGGESTION, and must
    # not leave behind a duplicate PRESENTED suggestion record alongside
    # the one that was actually accepted.
    flow_after_approve = client.get(
        f"/requests/{task_id}/flow",
        params={"database_url": database_url},
    ).json()
    assert flow_after_approve["status"] != "PENDING_SUGGESTION"
    assert flow_after_approve["suggestion"] is None

    suggestions_response = client.get(
        "/suggestions",
        params={"task_id": task_id, "database_url": database_url},
    )
    assert suggestions_response.json()["count"] == 1
    assert suggestions_response.json()["suggestions"][0]["status"] == "ACCEPTED"

    missing_conversation_response = client.post(
        "/conversations/does-not-exist/escalate",
        json={"content": "hi", "database_url": database_url},
    )
    assert missing_conversation_response.status_code == 404


def test_api_local_flow_and_observability_endpoints(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    flow_response = client.post(
        "/flows/local",
        json={
            "project_root": str(tmp_path),
            "context_path": "docs/INDEX.md",
            "title": "API integration flow",
            "database_url": database_url,
            "approve_suggestion": True,
        },
    )

    assert flow_response.status_code == 200
    flow_payload = flow_response.json()
    # PLAN is a gated stage like any other: /flows/local (like /requests)
    # stops at PLANNED after the first gated stage runs — it never jumps
    # ahead to IMPLEMENTED on its own.
    assert flow_payload["task_state"] == "PLANNED"
    assert flow_payload["execution_state"] == "COMPLETED"
    assert flow_payload["suggestion_status"] == "ACCEPTED"
    assert flow_payload["suggested_role"] == "TASK_PLANNER"
    assert flow_payload["suggested_action"] == "PLAN"

    audit_response = client.get(
        "/audit",
        params={"database_url": database_url, "task_id": flow_payload["task_id"]},
    )
    events_response = client.get(
        "/events",
        params={"database_url": database_url, "task_id": flow_payload["task_id"]},
    )
    metrics_response = client.get(
        "/metrics",
        params={"database_url": database_url, "task_id": flow_payload["task_id"]},
    )
    suggestions_response = client.get(
        "/suggestions",
        params={"database_url": database_url, "task_id": flow_payload["task_id"]},
    )
    tasks_response = client.get("/tasks", params={"database_url": database_url})
    task_response = client.get(
        f"/tasks/{flow_payload['task_id']}",
        params={"database_url": database_url},
    )
    authorizations_response = client.get(
        "/authorizations",
        params={
            "database_url": database_url,
            "task_id": flow_payload["task_id"],
        },
    )
    authorization_response = client.get(
        f"/authorizations/{flow_payload['authorization_id']}",
        params={"database_url": database_url},
    )
    authorization_request_response = client.post(
        "/authorizations/request",
        json={
            "task_id": flow_payload["task_id"],
            "role": "QUALITY_AGENT",
            "action": "REVIEW",
            "reason": "Need explicit review authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "context_scope": ["docs/INDEX.md"],
            "proposed_state": "REVIEWING",
            "database_url": database_url,
        },
    )
    executions_response = client.get(
        "/executions",
        params={"database_url": database_url},
    )
    execution_response = client.get(
        f"/executions/{flow_payload['execution_id']}",
        params={"database_url": database_url},
    )
    execution_context_response = client.get(
        f"/executions/{flow_payload['execution_id']}/context",
        params={"database_url": database_url},
    )

    assert audit_response.status_code == 200
    assert any(
        record["operation"] == "EXECUTION_COMPLETED"
        for record in audit_response.json()["records"]
    )
    assert events_response.status_code == 200
    assert any(
        event["event_type"] == "EXECUTION_COMPLETED"
        for event in events_response.json()["events"]
    )
    assert metrics_response.status_code == 200
    assert any(
        record["name"] == "execution.success"
        for record in metrics_response.json()["records"]
    )
    assert suggestions_response.status_code == 200
    assert suggestions_response.json()["suggestions"][0]["status"] == "ACCEPTED"
    assert tasks_response.status_code == 200
    assert tasks_response.json()["count"] >= 1
    assert task_response.status_code == 200
    assert task_response.json()["state"] == "PLANNED"
    assert "IMPLEMENTING" in task_response.json()["available_transitions"]
    assert authorizations_response.status_code == 200
    assert authorizations_response.json()["count"] == 1
    assert authorization_response.status_code == 200
    assert authorization_response.json()["status"] == "GRANTED"
    assert authorization_request_response.status_code == 200
    assert authorization_request_response.json()["status"] is None
    second_authorization_id = authorization_request_response.json()["authorization_id"]
    authorization_decision_response = client.post(
        f"/authorizations/{second_authorization_id}/decision",
        json={
            "status": "REJECTED",
            "decided_by": "review-manager",
            "reason": "Review deferred",
            "database_url": database_url,
        },
    )
    assert authorization_decision_response.status_code == 200
    assert authorization_decision_response.json()["status"] == "REJECTED"
    assert executions_response.status_code == 200
    assert executions_response.json()["count"] >= 1
    assert execution_response.status_code == 200
    assert execution_response.json()["state"] == "COMPLETED"
    assert execution_response.json()["available_transitions"] == []
    assert execution_context_response.status_code == 200
    assert execution_context_response.json()["count"] == 1
    assert (
        execution_context_response.json()["records"][0]["reference"]["resource"]
        == "docs/INDEX.md"
    )
    filtered_events_response = client.get(
        "/events",
        params={
            "database_url": database_url,
            "execution_id": flow_payload["execution_id"],
            "event_type": "EXECUTION_COMPLETED",
        },
    )
    filtered_audit_response = client.get(
        "/audit",
        params={
            "database_url": database_url,
            "execution_id": flow_payload["execution_id"],
            "authorization_id": flow_payload["authorization_id"],
        },
    )
    filtered_metrics_response = client.get(
        "/metrics",
        params={
            "database_url": database_url,
            "execution_id": flow_payload["execution_id"],
            "name": "execution.success",
        },
    )
    assert filtered_events_response.status_code == 200
    assert filtered_events_response.json()["count"] >= 1
    assert all(
        event["execution_id"] == flow_payload["execution_id"]
        and event["event_type"] == "EXECUTION_COMPLETED"
        for event in filtered_events_response.json()["events"]
    )
    assert filtered_audit_response.status_code == 200
    assert filtered_audit_response.json()["count"] >= 1
    assert all(
        record["execution_id"] == flow_payload["execution_id"]
        and record["authorization_id"] == flow_payload["authorization_id"]
        for record in filtered_audit_response.json()["records"]
    )
    assert filtered_metrics_response.status_code == 200
    assert filtered_metrics_response.json()["count"] >= 1
    assert all(
        record["execution_id"] == flow_payload["execution_id"]
        and record["name"] == "execution.success"
        for record in filtered_metrics_response.json()["records"]
    )


def test_api_metrics_summary_endpoint_aggregates(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    flow_response = client.post(
        "/flows/local",
        json={
            "project_root": str(tmp_path),
            "context_path": "docs/INDEX.md",
            "title": "Metrics summary flow",
            "database_url": database_url,
            "approve_suggestion": True,
        },
    )
    assert flow_response.status_code == 200
    flow_payload = flow_response.json()

    summary_response = client.get(
        "/metrics/summary",
        params={
            "database_url": database_url,
            "project_id": flow_payload["project_id"],
            "name": "execution.success",
            "group_by": "role,action",
        },
    )
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["count"] == 1
    bucket = summary_payload["summaries"][0]
    assert bucket["name"] == "execution.success"
    assert bucket["count"] == 1
    assert bucket["sum"] == 1.0
    assert bucket["dimensions"] == {"role": "TASK_PLANNER", "action": "PLAN"}

    unfiltered_response = client.get(
        "/metrics/summary",
        params={"database_url": database_url, "project_id": flow_payload["project_id"]},
    )
    assert unfiltered_response.status_code == 200
    names = {summary["name"] for summary in unfiltered_response.json()["summaries"]}
    assert "execution.success" in names
    assert "execution.duration" in names

    invalid_group_by_response = client.get(
        "/metrics/summary",
        params={
            "database_url": database_url,
            "group_by": "not_a_real_field",
        },
    )
    assert invalid_group_by_response.status_code == 400


def test_api_project_endpoints_cover_discovery_security_and_operations(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Project", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    register_response = client.post(
        "/projects",
        json={
            "project_root": str(tmp_path),
            "database_url": database_url,
        },
    )
    assert register_response.status_code == 200
    assert register_response.json()["name"] == tmp_path.name
    assert register_response.json()["observed_readiness_level"] == "LEVEL_2_VALIDATABLE"

    discover_response = client.get(
        "/projects/discover",
        params={"project_root": str(tmp_path), "limit": 5},
    )
    readiness_response = client.get(
        "/projects/readiness",
        params={"project_root": str(tmp_path)},
    )
    security_response = client.get(
        "/projects/security",
        params={"project_root": str(tmp_path)},
    )

    assert discover_response.status_code == 200
    assert any(
        resource["resource"] == "README.md"
        for resource in discover_response.json()["resources"]
    )
    assert readiness_response.status_code == 200
    assert readiness_response.json()["readiness_level"] == "LEVEL_2_VALIDATABLE"
    assert security_response.status_code == 200
    assert security_response.json()["allow_cloud_provider_sharing"] is False

    operation_response = client.post(
        "/projects/operations",
        json={
            "project_root": str(tmp_path),
            "operation": "WRITE_SOURCE",
            "resource": "src/api.py",
            "content": "print('api')",
            "database_url": database_url,
            "approve_operation": True,
        },
    )
    assert operation_response.status_code == 200
    operation_payload = operation_response.json()
    assert operation_payload["task_state"] == "IMPLEMENTED"
    assert (tmp_path / "src" / "api.py").read_text(encoding="utf-8") == "print('api')"

    projects_response = client.get("/projects", params={"database_url": database_url})
    assert projects_response.status_code == 200
    assert projects_response.json()["count"] == 1
    project_id = projects_response.json()["projects"][0]["project_id"]
    lookup_response = client.get(
        "/projects/lookup",
        params={"project_root": str(tmp_path), "database_url": database_url},
    )
    missing_lookup_response = client.get(
        "/projects/lookup",
        params={
            "project_root": str(tmp_path / "missing-project"),
            "database_url": database_url,
        },
    )
    assert lookup_response.status_code == 200
    assert lookup_response.json()["found"] is True
    assert lookup_response.json()["project"]["project_id"] == project_id
    assert missing_lookup_response.status_code == 200
    assert missing_lookup_response.json() == {"project": None, "found": False}

    update_response = client.patch(
        f"/projects/{project_id}/security",
        json={
            "database_url": database_url,
            "allow_cloud_provider_sharing": True,
            "persist_context_snapshots": True,
            "readiness_level": "LEVEL_3_AUTOMATABLE",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["security_profile"]["allow_cloud_provider_sharing"] is True
    assert update_response.json()["effective_readiness_level"] == "LEVEL_3_AUTOMATABLE"

    show_response = client.get(
        f"/projects/{project_id}",
        params={"database_url": database_url},
    )
    assert show_response.status_code == 200
    assert show_response.json()["security_profile"]["persist_context_snapshots"] is True

    settings_response = client.get("/settings/runtime", params={"database_url": database_url})
    capabilities_response = client.get(
        "/providers/capabilities",
        params={"database_url": database_url},
    )
    health_response = client.get(
        "/providers/health",
        params={"database_url": database_url},
    )
    runtime_check_response = client.get(
        "/runtime/check",
        params={"database_url": database_url},
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["database"]["is_sqlite"] is True
    assert settings_response.json()["database"]["operational_role"] == "local-only"
    assert capabilities_response.status_code == 200
    assert capabilities_response.json()["provider"] == "stub"
    assert health_response.status_code == 200
    assert health_response.json()["reachable"] is True
    assert runtime_check_response.status_code == 200
    assert runtime_check_response.json()["ready"] is True
    assert runtime_check_response.json()["operational_mode"] == "local-only"
    assert runtime_check_response.json()["database"]["reachable"] is True
    assert runtime_check_response.json()["provider"]["reachable"] is True
    assert runtime_check_response.json()["warnings"]

    sync_response = client.post(
        "/admin/db/sync",
        json={"database_url": database_url},
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["create_status"] == "skipped_non_postgresql"
    assert sync_response.json()["migrations"] == "applied"
    assert "local-flow" in sync_response.json()["message"]

    policy_allowed_response = client.post(
        "/policies/evaluate",
        json={
            "execution_mode": "MANUAL",
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "requested_model": "local-demo",
            "effective_model": "local-demo",
            "current_task_state": "PLANNED",
            "project_operation": "WRITE_SOURCE",
            "project_root": str(tmp_path),
            "explicit_user_command": True,
            "database_url": database_url,
        },
    )
    policy_blocked_response = client.post(
        "/policies/evaluate",
        json={
            "execution_mode": "SUGGESTED",
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "requested_model": "local-demo",
            "effective_model": "local-demo",
            "current_task_state": "PLANNED",
            "project_operation": "WRITE_SOURCE",
            "project_root": str(tmp_path),
            "database_url": database_url,
        },
    )
    assert policy_allowed_response.status_code == 200
    assert policy_allowed_response.json()["allowed"] is True
    assert policy_allowed_response.json()["reason"] == "manual_mode_direct_command"
    assert policy_blocked_response.status_code == 200
    assert policy_blocked_response.json()["allowed"] is False
    assert policy_blocked_response.json()["reason"] == "suggested_mode_requires_approval"


def test_api_automatic_policy_get_and_put_round_trip(tmp_path) -> None:
    client = TestClient(app)
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"

    default_response = client.get(
        "/policies/automatic",
        params={"database_url": database_url},
    )
    assert default_response.status_code == 200
    assert default_response.json() == {
        "allowed_operations": [{"role": "DEVELOPER", "action": "IMPLEMENT"}],
        "allowed_cross_role_transitions": [],
        "allow_model_substitution": False,
        "allow_context_expansion": False,
    }

    put_response = client.put(
        "/policies/automatic",
        json={
            "allowed_operations": [{"role": "DEVELOPER", "action": "IMPLEMENT"}],
            "allowed_cross_role_transitions": [
                {"previous_role": "DEVELOPER", "next_role": "QUALITY_AGENT"}
            ],
            "allow_model_substitution": True,
            "allow_context_expansion": False,
            "database_url": database_url,
        },
    )
    assert put_response.status_code == 200
    assert put_response.json() == {
        "allowed_operations": [{"role": "DEVELOPER", "action": "IMPLEMENT"}],
        "allowed_cross_role_transitions": [
            {"previous_role": "DEVELOPER", "next_role": "QUALITY_AGENT"}
        ],
        "allow_model_substitution": True,
        "allow_context_expansion": False,
    }

    get_after_put_response = client.get(
        "/policies/automatic",
        params={"database_url": database_url},
    )
    assert get_after_put_response.status_code == 200
    assert get_after_put_response.json() == put_response.json()


def test_api_health_endpoint_reports_version() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0"}


def test_api_direct_task_and_execution_lifecycle_endpoints(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)
    project_response = client.post(
        "/projects",
        json={
            "project_root": str(tmp_path),
            "database_url": database_url,
        },
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["project_id"]

    task_response = client.post(
        "/tasks",
        json={
            "title": "Direct lifecycle task",
            "description": "Created through API",
            "requested_change": "Implement API lifecycle coverage",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "acceptance_criteria": ["passes tests"],
            "database_url": database_url,
        },
    )
    assert task_response.status_code == 200
    task_payload = task_response.json()
    assert task_payload["state"] == "CREATED"
    assert "PLANNING" in task_payload["available_transitions"]

    transitioned_task_response = client.post(
        f"/tasks/{task_payload['task_id']}/transition",
        json={
            "target_state": "PLANNING",
            "database_url": database_url,
        },
    )
    assert transitioned_task_response.status_code == 200
    assert transitioned_task_response.json()["state"] == "PLANNING"
    assert "PLANNED" in transitioned_task_response.json()["available_transitions"]

    authorization_response = client.post(
        "/authorizations/request",
        json={
            "task_id": task_payload["task_id"],
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "context_scope": ["README.md"],
            "database_url": database_url,
        },
    )
    assert authorization_response.status_code == 200
    authorization_id = authorization_response.json()["authorization_id"]

    decision_response = client.post(
        f"/authorizations/{authorization_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "api-manager",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["status"] == "GRANTED"

    execution_response = client.post(
        "/executions/request",
        json={
            "task_id": task_payload["task_id"],
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "model_id": "local-demo",
            "authorization_id": authorization_id,
            "project_id": project_id,
            "requested_context": ["README.md"],
            "authorized_context": ["README.md"],
            "database_url": database_url,
        },
    )
    assert execution_response.status_code == 200
    execution_payload = execution_response.json()
    assert execution_payload["state"] == "AUTHORIZED"
    assert "PREPARING" in execution_payload["available_transitions"]

    preparing_response = client.post(
        f"/executions/{execution_payload['execution_id']}/transition",
        json={
            "target_state": "PREPARING",
            "database_url": database_url,
        },
    )
    started_response = client.post(
        f"/executions/{execution_payload['execution_id']}/transition",
        json={
            "target_state": "STARTED",
            "database_url": database_url,
        },
    )
    running_response = client.post(
        f"/executions/{execution_payload['execution_id']}/transition",
        json={
            "target_state": "RUNNING",
            "database_url": database_url,
        },
    )
    assert preparing_response.status_code == 200
    assert preparing_response.json()["state"] == "PREPARING"
    assert "STARTED" in preparing_response.json()["available_transitions"]
    assert started_response.status_code == 200
    assert started_response.json()["state"] == "STARTED"
    assert "RUNNING" in started_response.json()["available_transitions"]
    assert running_response.status_code == 200
    assert running_response.json()["state"] == "RUNNING"
    assert "COMPLETED" in running_response.json()["available_transitions"]

    completed_response = client.post(
        f"/executions/{execution_payload['execution_id']}/complete",
        json={
            "output": "Implemented through direct lifecycle",
            "success": True,
            "warnings": ["none"],
            "resource_usage": {
                "input_tokens": 10,
                "output_tokens": 15,
                "estimated_cost": 0.01,
            },
            "database_url": database_url,
        },
    )
    assert completed_response.status_code == 200
    assert completed_response.json()["state"] == "COMPLETED"
    assert completed_response.json()["available_transitions"] == []
    assert completed_response.json()["result"]["success"] is True
    resolved_context_response = client.post(
        f"/executions/{execution_payload['execution_id']}/resolve-context",
        json={
            "source": "SOURCE_FILE",
            "database_url": database_url,
        },
    )
    assert resolved_context_response.status_code == 200
    assert resolved_context_response.json()["count"] == 1
    assert resolved_context_response.json()["items"][0]["reference"]["resource"] == "README.md"


def test_api_cancel_execution_endpoint_transitions_to_cancelled(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_id = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    ).json()["project_id"]
    task_id = client.post(
        "/tasks",
        json={
            "title": "Cancel target",
            "description": "Created through API",
            "requested_change": "N/A",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    ).json()["task_id"]
    client.post(
        f"/tasks/{task_id}/transition",
        json={"target_state": "PLANNING", "database_url": database_url},
    )
    authorization_id = client.post(
        "/authorizations/request",
        json={
            "task_id": task_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "context_scope": ["README.md"],
            "database_url": database_url,
        },
    ).json()["authorization_id"]
    client.post(
        f"/authorizations/{authorization_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "api-manager",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    execution_id = client.post(
        "/executions/request",
        json={
            "task_id": task_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "model_id": "local-demo",
            "authorization_id": authorization_id,
            "project_id": project_id,
            "requested_context": ["README.md"],
            "authorized_context": ["README.md"],
            "database_url": database_url,
        },
    ).json()["execution_id"]

    cancel_response = client.post(
        f"/executions/{execution_id}/cancel",
        json={"database_url": database_url},
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["state"] == "CANCELLED"
    assert cancel_response.json()["available_transitions"] == []

    already_terminal_response = client.post(
        f"/executions/{execution_id}/cancel",
        json={"database_url": database_url},
    )
    assert already_terminal_response.status_code == 200
    assert already_terminal_response.json()["state"] == "CANCELLED"


def test_api_run_execution_endpoint_drives_execution_engine(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={
            "project_root": str(tmp_path),
            "database_url": database_url,
        },
    )
    task_response = client.post(
        "/tasks",
        json={
            "title": "Run execution task",
            "description": "Drive execution engine through API",
            "requested_change": "Run with stub provider",
            "project_id": project_response.json()["project_id"],
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    authorization_response = client.post(
        "/authorizations/request",
        json={
            "task_id": task_response.json()["task_id"],
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "context_scope": ["README.md"],
            "database_url": database_url,
        },
    )
    authorization_id = authorization_response.json()["authorization_id"]
    client.post(
        f"/authorizations/{authorization_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "api-manager",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    execution_response = client.post(
        "/executions/request",
        json={
            "task_id": task_response.json()["task_id"],
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "model_id": "local-demo",
            "authorization_id": authorization_id,
            "project_id": project_response.json()["project_id"],
            "requested_context": ["README.md"],
            "authorized_context": ["README.md"],
            "database_url": database_url,
        },
    )
    execution_id = execution_response.json()["execution_id"]

    run_response = client.post(
        f"/executions/{execution_id}/run",
        params={"database_url": database_url},
    )

    assert run_response.status_code == 200
    assert run_response.json()["state"] == "COMPLETED"
    assert run_response.json()["result"]["success"] is True


def test_api_dispatch_execution_endpoint_schedules_async_execution(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={
            "project_root": str(tmp_path),
            "database_url": database_url,
        },
    )
    task_response = client.post(
        "/tasks",
        json={
            "title": "Dispatch execution task",
            "description": "Drive async execution dispatch through API",
            "requested_change": "Dispatch with stub provider",
            "project_id": project_response.json()["project_id"],
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    authorization_response = client.post(
        "/authorizations/request",
        json={
            "task_id": task_response.json()["task_id"],
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "context_scope": ["README.md"],
            "database_url": database_url,
        },
    )
    authorization_id = authorization_response.json()["authorization_id"]
    client.post(
        f"/authorizations/{authorization_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "api-manager",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    execution_response = client.post(
        "/executions/request",
        json={
            "task_id": task_response.json()["task_id"],
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "model_id": "local-demo",
            "authorization_id": authorization_id,
            "project_id": project_response.json()["project_id"],
            "requested_context": ["README.md"],
            "authorized_context": ["README.md"],
            "database_url": database_url,
        },
    )
    execution_id = execution_response.json()["execution_id"]

    dispatch_response = client.post(
        f"/executions/{execution_id}/dispatch",
        params={"database_url": database_url},
    )

    assert dispatch_response.status_code == 200
    assert dispatch_response.json()["dispatched"] is True
    assert dispatch_response.json()["active_in_process"] is True

    final_response = None
    for _ in range(20):
        time.sleep(0.05)
        final_response = client.get(
            f"/executions/{execution_id}",
            params={"database_url": database_url},
        )
        if final_response.json()["state"] == "COMPLETED":
            break

    assert final_response is not None
    assert final_response.status_code == 200
    assert final_response.json()["state"] == "COMPLETED"
    assert final_response.json()["result"]["success"] is True


def test_api_task_and_execution_lists_support_operational_filters(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    )
    project_id = project_response.json()["project_id"]

    first_task_response = client.post(
        "/tasks",
        json={
            "title": "First task",
            "description": "Created through API",
            "requested_change": "Implement first feature",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    second_task_response = client.post(
        "/tasks",
        json={
            "title": "Second task",
            "description": "Created through API",
            "requested_change": "Implement second feature",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    first_task_id = first_task_response.json()["task_id"]
    second_task_id = second_task_response.json()["task_id"]

    client.post(
        f"/tasks/{first_task_id}/transition",
        json={"target_state": "PLANNING", "database_url": database_url},
    )

    authorization_response = client.post(
        "/authorizations/request",
        json={
            "task_id": first_task_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "context_scope": ["README.md"],
            "database_url": database_url,
        },
    )
    authorization_id = authorization_response.json()["authorization_id"]
    client.post(
        f"/authorizations/{authorization_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "api-manager",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    execution_response = client.post(
        "/executions/request",
        json={
            "task_id": first_task_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "model_id": "local-demo",
            "authorization_id": authorization_id,
            "project_id": project_id,
            "requested_context": ["README.md"],
            "authorized_context": ["README.md"],
            "database_url": database_url,
        },
    )
    execution_id = execution_response.json()["execution_id"]
    client.post(
        f"/executions/{execution_id}/transition",
        json={"target_state": "PREPARING", "database_url": database_url},
    )

    filtered_tasks = client.get(
        "/tasks",
        params={
            "database_url": database_url,
            "project_id": project_id,
            "state": "PLANNING",
            "limit": 5,
        },
    )
    filtered_executions = client.get(
        "/executions",
        params={
            "database_url": database_url,
            "task_id": first_task_id,
            "project_id": project_id,
            "state": "PREPARING",
            "limit": 5,
        },
    )

    assert filtered_tasks.status_code == 200
    assert filtered_tasks.json()["count"] == 1
    assert filtered_tasks.json()["tasks"][0]["task_id"] == first_task_id
    assert filtered_tasks.json()["tasks"][0]["state"] == "PLANNING"
    assert all(
        task["task_id"] != second_task_id for task in filtered_tasks.json()["tasks"]
    )
    assert filtered_executions.status_code == 200
    assert filtered_executions.json()["count"] == 1
    assert filtered_executions.json()["executions"][0]["task_id"] == first_task_id
    assert filtered_executions.json()["executions"][0]["state"] == "PREPARING"


def test_api_task_snapshot_returns_consolidated_operational_view(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    )
    task_response = client.post(
        "/tasks",
        json={
            "title": "Snapshot task",
            "description": "Build task-centric snapshot",
            "requested_change": "Aggregate one operational view",
            "project_id": project_response.json()["project_id"],
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    task_id = task_response.json()["task_id"]
    authorization_response = client.post(
        "/authorizations/request",
        json={
            "task_id": task_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "api-test",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "context_scope": ["README.md"],
            "database_url": database_url,
        },
    )
    authorization_id = authorization_response.json()["authorization_id"]
    client.post(
        f"/authorizations/{authorization_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "api-manager",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    execution_response = client.post(
        "/executions/request",
        json={
            "task_id": task_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "model_id": "local-demo",
            "authorization_id": authorization_id,
            "project_id": project_response.json()["project_id"],
            "requested_context": ["README.md"],
            "authorized_context": ["README.md"],
            "database_url": database_url,
        },
    )
    execution_id = execution_response.json()["execution_id"]
    client.post(
        f"/executions/{execution_id}/run",
        params={"database_url": database_url},
    )

    snapshot_response = client.get(
        f"/tasks/{task_id}/snapshot",
        params={"database_url": database_url, "history_limit": 50},
    )

    assert snapshot_response.status_code == 200
    payload = snapshot_response.json()
    assert payload["task"]["task_id"] == task_id
    assert payload["counts"]["authorizations"] == 1
    assert payload["counts"]["executions"] == 1
    assert payload["counts"]["events"] >= 1
    assert payload["counts"]["audit_records"] >= 1
    assert payload["counts"]["metric_records"] >= 1
    assert payload["counts"]["context_records"] >= 1
    assert payload["executions"][0]["execution_id"] == execution_id
    assert payload["authorizations"][0]["authorization_id"] == authorization_id


def test_api_task_advance_runs_task_centric_workflow_to_documentation(tmp_path) -> None:
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
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    )
    task_response = client.post(
        "/tasks",
        json={
            "title": "Workflow task",
            "description": "Advance through staged orchestration",
            "requested_change": "Plan, implement, validate, test, and document",
            "project_id": project_response.json()["project_id"],
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    task_id = task_response.json()["task_id"]

    for expected_stage, expected_state in (
        ("PLAN", "PLANNED"),
        ("IMPLEMENT", "IMPLEMENTED"),
        ("REVIEW", "REVIEWING"),
        ("VALIDATE", "VALIDATING"),
    ):
        response = client.post(
            f"/tasks/{task_id}/advance",
            json={
                "context_paths": ["docs/INDEX.md"],
                "approve_stage": True,
                "database_url": database_url,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["stage"] == expected_stage
        assert payload["task_state"] == expected_state
        assert payload["authorization_id"]
        assert payload["execution_id"]
        assert payload["execution_state"] == "COMPLETED"
        assert payload["blocked_reason"] == ""

    test_response = client.post(
        f"/tasks/{task_id}/advance",
        json={
            "stage": "TEST",
            "approve_stage": True,
            "database_url": database_url,
        },
    )
    assert test_response.status_code == 200
    assert test_response.json()["stage"] == "TEST"
    assert test_response.json()["task_state"] == "VALIDATED"
    assert test_response.json()["blocked_reason"] == ""

    document_response = client.post(
        f"/tasks/{task_id}/advance",
        json={
            "stage": "DOCUMENT",
            "context_paths": ["docs/INDEX.md"],
            "documentation_path": "docs/RESULT.md",
            "approve_stage": True,
            "database_url": database_url,
        },
    )
    assert document_response.status_code == 200
    document_payload = document_response.json()
    assert document_payload["stage"] == "DOCUMENT"
    assert document_payload["task_state"] == "COMPLETED"
    assert document_payload["resource"] == "docs/RESULT.md"
    assert document_payload["execution_state"] == "COMPLETED"
    assert document_payload["blocked_reason"] == ""
    assert "Stub provider processed" in document_payload["output"]
    assert "Stub provider processed" in (docs / "RESULT.md").read_text(encoding="utf-8")


def test_api_requests_flow_reports_pending_suggestion_when_approval_is_withheld(
    tmp_path,
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    create_response = client.post(
        "/requests",
        json={
            "project_root": str(tmp_path),
            "prompt": "Implement the feature described in README.md",
            "context_paths": ["README.md"],
            "database_url": database_url,
        },
    )
    assert create_response.status_code == 200
    request_payload = create_response.json()
    request_id = request_payload["request_id"]

    # SUGGESTED mode without approve_suggestion is expected to stop short of
    # authorization, leaving a PRESENTED suggestion awaiting user decision.
    assert request_payload["status"] == "PENDING_SUGGESTION"
    assert request_payload["suggestion"]["status"] == "PRESENTED"

    flow_response = client.get(
        f"/requests/{request_id}/flow",
        params={"database_url": database_url},
    )
    assert flow_response.status_code == 200
    flow_payload = flow_response.json()
    assert flow_payload["status"] == "PENDING_SUGGESTION"
    assert flow_payload["suggestion"]["status"] == "PRESENTED"
    assert flow_payload["pending_authorization_id"] is None


def test_api_requests_approve_endpoint_resolves_presented_suggestion_via_advance(
    tmp_path,
) -> None:
    """Regression test for the gap where /approve could not resolve the most
    common SUGGESTED-mode case: run_task_workflow_stage returns before ever
    creating an Authorization when policy blocks, so only a PRESENTED
    suggestion exists — no pending Authorization for /approve to find. This
    confirms /approve now delegates internally to the same gated mechanism
    used by /advance (approve_stage=true) instead of always reporting
    "no_pending_authorization" in this case.
    """

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("Project docs", encoding="utf-8")
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    create_response = client.post(
        "/requests",
        json={
            "project_root": str(tmp_path),
            "prompt": "Implement the feature described in README.md",
            "context_paths": ["README.md"],
            "database_url": database_url,
        },
    )
    assert create_response.status_code == 200
    request_payload = create_response.json()
    request_id = request_payload["request_id"]
    assert request_payload["status"] == "PENDING_SUGGESTION"

    # No standalone Authorization exists yet — only the PRESENTED suggestion.
    flow_before_response = client.get(
        f"/requests/{request_id}/flow",
        params={"database_url": database_url},
    )
    assert flow_before_response.json()["pending_authorization_id"] is None

    approve_response = client.post(
        f"/requests/{request_id}/approve",
        json={
            "decided_by": "chat-user",
            "reason": "Approve the PLAN stage",
            "context_paths": ["README.md"],
            "database_url": database_url,
        },
    )
    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["approved"] is True
    assert approve_payload["blocked_reason"] == ""
    assert approve_payload["task_state"] == "PLANNED"
    assert approve_payload["suggested_role"] == "TASK_PLANNER"
    assert approve_payload["suggested_action"] == "PLAN"
    assert approve_payload["suggestion_status"] == "ACCEPTED"

    flow_after_response = client.get(
        f"/requests/{request_id}/flow",
        params={"database_url": database_url},
    )
    assert flow_after_response.json()["task"]["state"] == "PLANNED"


def test_api_requests_approve_endpoint_finds_and_grants_pending_authorization(
    tmp_path,
) -> None:
    """Regression test for a fixed bug: POST /requests/{id}/approve and the
    derived flow status used to compare authorization/suggestion status
    against a literal "PENDING" string that neither AuthorizationDecisionStatus
    nor SuggestionStatus defines, so a genuinely pending authorization could
    never be found. This exercises the mixed chat-first/operational usage
    where an authorization is requested through the fine-grained surface and
    then decided through the chat-first /requests/{id}/approve endpoint.
    """

    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_response = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    )
    project_id = project_response.json()["project_id"]

    task_response = client.post(
        "/tasks",
        json={
            "title": "Approve-flow regression task",
            "description": "Covers the chat-first approve endpoint",
            "requested_change": "Implement a change requiring authorization",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    )
    request_id = task_response.json()["task_id"]

    authorization_response = client.post(
        "/authorizations/request",
        json={
            "task_id": request_id,
            "role": "DEVELOPER",
            "action": "IMPLEMENT",
            "reason": "Need execution authorization",
            "requester": "chat-user",
            "execution_mode": "SUGGESTED",
            "model_id": "local-demo",
            "database_url": database_url,
        },
    )
    assert authorization_response.status_code == 200
    authorization_id = authorization_response.json()["authorization_id"]

    # Before any decision is recorded, the authorization is pending and the
    # derived flow status/pending id must reflect it.
    flow_before_response = client.get(
        f"/requests/{request_id}/flow",
        params={"database_url": database_url},
    )
    assert flow_before_response.status_code == 200
    flow_before = flow_before_response.json()
    assert flow_before["status"] == "PENDING_AUTHORIZATION"
    assert flow_before["pending_authorization_id"] == authorization_id

    approve_response = client.post(
        f"/requests/{request_id}/approve",
        json={
            "decided_by": "chat-user",
            "reason": "Looks good, proceed.",
            "database_url": database_url,
        },
    )
    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["approved"] is True
    assert approve_payload["status"] == "GRANTED"
    assert approve_payload["authorization_id"] == authorization_id

    authorization_show_response = client.get(
        f"/authorizations/{authorization_id}",
        params={"database_url": database_url},
    )
    assert authorization_show_response.status_code == 200
    assert authorization_show_response.json()["status"] == "GRANTED"

    # A second approve call now finds nothing pending.
    second_approve_response = client.post(
        f"/requests/{request_id}/approve",
        json={
            "decided_by": "chat-user",
            "reason": "N/A",
            "database_url": database_url,
        },
    )
    assert second_approve_response.status_code == 200
    assert second_approve_response.json()["approved"] is False
    assert second_approve_response.json()["status"] == "no_pending_authorization"


def test_api_authorizations_list_supports_status_and_pending_only_filters(
    tmp_path,
) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_id = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    ).json()["project_id"]
    task_id = client.post(
        "/tasks",
        json={
            "title": "Authorization filter task",
            "description": "Covers authorization list filters",
            "requested_change": "Implement a change",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    ).json()["task_id"]

    def _request_authorization() -> str:
        response = client.post(
            "/authorizations/request",
            json={
                "task_id": task_id,
                "role": "DEVELOPER",
                "action": "IMPLEMENT",
                "reason": "Need execution authorization",
                "requester": "filter-test",
                "execution_mode": "SUGGESTED",
                "model_id": "local-demo",
                "database_url": database_url,
            },
        )
        assert response.status_code == 200
        return response.json()["authorization_id"]

    granted_id = _request_authorization()
    pending_id = _request_authorization()

    decision_response = client.post(
        f"/authorizations/{granted_id}/decision",
        json={
            "status": "GRANTED",
            "decided_by": "filter-test",
            "reason": "Approved",
            "database_url": database_url,
        },
    )
    assert decision_response.status_code == 200

    all_response = client.get(
        "/authorizations",
        params={"task_id": task_id, "database_url": database_url},
    )
    assert all_response.status_code == 200
    assert all_response.json()["count"] == 2

    pending_response = client.get(
        "/authorizations",
        params={"task_id": task_id, "pending_only": True, "database_url": database_url},
    )
    assert pending_response.status_code == 200
    pending_payload = pending_response.json()
    assert pending_payload["count"] == 1
    assert pending_payload["authorizations"][0]["authorization_id"] == pending_id

    granted_response = client.get(
        "/authorizations",
        params={"task_id": task_id, "status": "GRANTED", "database_url": database_url},
    )
    assert granted_response.status_code == 200
    granted_payload = granted_response.json()
    assert granted_payload["count"] == 1
    assert granted_payload["authorizations"][0]["authorization_id"] == granted_id


def test_api_audit_show_endpoint_returns_matching_record(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_id = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    ).json()["project_id"]
    task_id = client.post(
        "/tasks",
        json={
            "title": "Audit show task",
            "description": "Covers GET /audit/{id}",
            "requested_change": "Implement a change",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    ).json()["task_id"]

    list_response = client.get(
        "/audit",
        params={"task_id": task_id, "database_url": database_url},
    )
    assert list_response.status_code == 200
    records = list_response.json()["records"]
    assert records, "expected at least one audit record from task creation"
    audit_id = records[0]["audit_id"]

    show_response = client.get(
        f"/audit/{audit_id}",
        params={"database_url": database_url},
    )
    assert show_response.status_code == 200
    show_payload = show_response.json()
    assert show_payload["audit_id"] == audit_id
    assert show_payload == records[0]


def test_api_suggestions_show_generate_accept_reject_endpoints(tmp_path) -> None:
    (tmp_path / ".git").mkdir()
    database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
    client = TestClient(app)

    project_id = client.post(
        "/projects",
        json={"project_root": str(tmp_path), "database_url": database_url},
    ).json()["project_id"]
    task_id = client.post(
        "/tasks",
        json={
            "title": "Suggestion lifecycle task",
            "description": "Covers suggestion generate/show/accept/reject",
            "requested_change": "Implement a change",
            "project_id": project_id,
            "execution_mode": "SUGGESTED",
            "database_url": database_url,
        },
    ).json()["task_id"]

    transition_response = client.post(
        f"/tasks/{task_id}/transition",
        json={"target_state": "PLANNING", "database_url": database_url},
    )
    assert transition_response.status_code == 200

    generate_response = client.post(
        f"/tasks/{task_id}/suggestions",
        params={"database_url": database_url},
    )
    assert generate_response.status_code == 200
    generate_payload = generate_response.json()
    assert generate_payload["task_id"] == task_id
    suggestion = generate_payload["suggestion"]
    assert suggestion is not None
    assert suggestion["status"] == "GENERATED"
    suggestion_id = suggestion["suggestion_id"]

    show_response = client.get(
        f"/suggestions/{suggestion_id}",
        params={"database_url": database_url},
    )
    assert show_response.status_code == 200
    assert show_response.json()["suggestion_id"] == suggestion_id

    accept_response = client.post(
        f"/suggestions/{suggestion_id}/accept",
        params={"database_url": database_url},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "ACCEPTED"

    reject_response = client.post(
        f"/suggestions/{suggestion_id}/reject",
        params={"database_url": database_url},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "REJECTED"


def test_api_auth_login_refresh_logout_round_trip(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    _create_user(username="alice", password="correct horse battery", is_superuser=False)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login", json={"username": "alice", "password": "correct horse battery"}
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["user"]["username"] == "alice"
    assert login_payload["token_type"] == "bearer"
    assert login_payload["access_token"]
    assert login_payload["refresh_token"]

    bad_login_response = client.post(
        "/auth/login", json={"username": "alice", "password": "wrong password"}
    )
    assert bad_login_response.status_code == 401

    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": login_payload["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["access_token"]
    assert refresh_payload["refresh_token"] != login_payload["refresh_token"]

    # The rotated-out refresh token is no longer usable.
    stale_refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": login_payload["refresh_token"]}
    )
    assert stale_refresh_response.status_code == 401

    logout_response = client.post(
        "/auth/logout", json={"refresh_token": refresh_payload["refresh_token"]}
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "logged_out"

    logged_out_refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": refresh_payload["refresh_token"]}
    )
    assert logged_out_refresh_response.status_code == 401


def test_api_unenforced_by_default_allows_requests_without_a_token(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("ORCHAI_AUTH_ENFORCED", raising=False)
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    client = TestClient(app)

    response = client.get("/providers/settings")

    assert response.status_code == 200


def test_api_enforced_requires_a_valid_bearer_token(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="bob", password="correct horse battery", is_superuser=True)
    client = TestClient(app)

    unauthenticated_response = client.get("/providers/settings")
    assert unauthenticated_response.status_code == 401

    malformed_response = client.get(
        "/providers/settings", headers={"Authorization": "not-a-bearer-token"}
    )
    assert malformed_response.status_code == 401

    invalid_token_response = client.get(
        "/providers/settings", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert invalid_token_response.status_code == 401

    login_response = client.post(
        "/auth/login", json={"username": "bob", "password": "correct horse battery"}
    )
    access_token = login_response.json()["access_token"]

    authenticated_response = client.get(
        "/providers/settings", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert authenticated_response.status_code == 200


def test_api_enforced_superuser_bypasses_permission_checks(
    monkeypatch, tmp_path
) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    client = TestClient(app)

    access_token = client.post(
        "/auth/login", json={"username": "root", "password": "correct horse battery"}
    ).json()["access_token"]

    # /projects requires "projects:read"; a superuser needs no explicit grant.
    response = client.get(
        "/projects",
        params={"database_url": database_url},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200


def test_api_enforced_rejects_a_user_missing_the_required_permission(
    monkeypatch, tmp_path
) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(
        username="scoped", password="correct horse battery", is_superuser=False
    )
    client = TestClient(app)

    access_token = client.post(
        "/auth/login",
        json={"username": "scoped", "password": "correct horse battery"},
    ).json()["access_token"]

    # /projects requires "projects:read", which "scoped" was never granted.
    response = client.get(
        "/projects",
        params={"database_url": database_url},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403

    # An endpoint that only requires authentication (no specific
    # permission) still succeeds for the same, unprivileged user.
    authenticated_only_response = client.get(
        "/providers/settings", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert authenticated_only_response.status_code == 200


def test_api_enforced_rejects_writing_automatic_policy_without_manage_permission(
    monkeypatch, tmp_path
) -> None:
    """`policies:manage` is a distinct permission from `policies:evaluate` --
    a user with neither can read nor write the automatic policy."""

    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(
        username="scoped", password="correct horse battery", is_superuser=False
    )
    client = TestClient(app)

    access_token = client.post(
        "/auth/login",
        json={"username": "scoped", "password": "correct horse battery"},
    ).json()["access_token"]

    put_response = client.put(
        "/policies/automatic",
        json={"database_url": database_url},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert put_response.status_code == 403

    get_response = client.get(
        "/policies/automatic",
        params={"database_url": database_url},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert get_response.status_code == 403


# ---------------------------------------------------------------------------
# User-configuration CRUD (admin + self-service, ADR-012)
# ---------------------------------------------------------------------------


def _permission_id_map() -> dict[str, str]:
    """Return {permission_key: permission_id} from the auto-seeded catalog.

    There is no `GET /admin/permissions` endpoint (permissions are a fixed
    system catalog, not admin-creatable -- only role<->permission
    assignment is), so tests that need a permission id for a
    `PUT /admin/access-roles/{id}/permissions` body resolve it directly
    through the identity service, exactly like `_create_user` reaches the
    identity DB directly for setup.
    """

    identity_runtime = build_identity_runtime_from_settings(load_settings())
    permissions = asyncio.run(identity_runtime.identity_service.list_permissions(limit=100))
    return {permission.key: str(permission.id) for permission in permissions}


def test_api_admin_access_role_and_user_crud_flow(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    client = TestClient(app)
    root_token = client.post(
        "/auth/login", json={"username": "root", "password": "correct horse battery"}
    ).json()["access_token"]
    root_headers = {"Authorization": f"Bearer {root_token}"}

    create_role_response = client.post(
        "/admin/access-roles",
        json={"name": "Engineer", "description": "Engineering role"},
        headers=root_headers,
    )
    assert create_role_response.status_code == 200
    role_id = create_role_response.json()["role_id"]

    # Duplicate access-role names are rejected.
    duplicate_role_response = client.post(
        "/admin/access-roles", json={"name": "Engineer"}, headers=root_headers
    )
    assert duplicate_role_response.status_code == 409

    permission_ids = _permission_id_map()
    set_permissions_response = client.put(
        f"/admin/access-roles/{role_id}/permissions",
        json={
            "permission_ids": [
                permission_ids["projects:read"],
                permission_ids["requests:create"],
            ]
        },
        headers=root_headers,
    )
    assert set_permissions_response.status_code == 200
    assert sorted(
        p["key"] for p in set_permissions_response.json()["permissions"]
    ) == ["projects:read", "requests:create"]

    # Creating a non-superuser with zero access roles is rejected.
    no_role_response = client.post(
        "/admin/users",
        json={"username": "norole", "password": "correct horse battery"},
        headers=root_headers,
    )
    assert no_role_response.status_code == 400

    create_user_response = client.post(
        "/admin/users",
        json={
            "username": "alice",
            "password": "correct horse battery",
            "role_ids": [role_id],
        },
        headers=root_headers,
    )
    assert create_user_response.status_code == 200
    alice_payload = create_user_response.json()
    assert alice_payload["access_roles"] == [{"role_id": role_id, "name": "Engineer"}]
    assert "password" not in alice_payload
    assert "password_hash" not in alice_payload
    alice_id = alice_payload["user_id"]

    list_users_response = client.get("/admin/users", headers=root_headers)
    assert list_users_response.status_code == 200
    usernames = {u["username"] for u in list_users_response.json()["users"]}
    assert {"root", "alice"} <= usernames

    list_roles_response = client.get("/admin/access-roles", headers=root_headers)
    assert list_roles_response.status_code == 200
    engineer_role = next(
        r for r in list_roles_response.json()["access_roles"] if r["role_id"] == role_id
    )
    assert engineer_role["users"] == [{"user_id": alice_id, "username": "alice"}]

    # Replacing alice's roles down to zero is rejected (she is not a superuser).
    empty_roles_response = client.put(
        f"/admin/users/{alice_id}/access-roles",
        json={"role_ids": []},
        headers=root_headers,
    )
    assert empty_roles_response.status_code == 400

    second_role_response = client.post(
        "/admin/access-roles", json={"name": "Reviewer"}, headers=root_headers
    )
    second_role_id = second_role_response.json()["role_id"]
    replace_roles_response = client.put(
        f"/admin/users/{alice_id}/access-roles",
        json={"role_ids": [second_role_id]},
        headers=root_headers,
    )
    assert replace_roles_response.status_code == 200
    assert replace_roles_response.json()["access_roles"] == [
        {"role_id": second_role_id, "name": "Reviewer"}
    ]

    # A non-admin user is rejected from every admin endpoint.
    alice_token = client.post(
        "/auth/login", json={"username": "alice", "password": "correct horse battery"}
    ).json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    assert client.get("/admin/users", headers=alice_headers).status_code == 403
    assert client.get("/admin/access-roles", headers=alice_headers).status_code == 403
    assert (
        client.post("/admin/access-roles", json={"name": "X"}, headers=alice_headers).status_code
        == 403
    )


def test_api_admin_projects_lists_capabilities_and_connected_users(
    monkeypatch, tmp_path
) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    client = TestClient(app)
    root_token = client.post(
        "/auth/login", json={"username": "root", "password": "correct horse battery"}
    ).json()["access_token"]
    root_headers = {"Authorization": f"Bearer {root_token}"}

    role_id = client.post(
        "/admin/access-roles", json={"name": "Connector"}, headers=root_headers
    ).json()["role_id"]
    permission_ids = _permission_id_map()
    client.put(
        f"/admin/access-roles/{role_id}/permissions",
        json={
            "permission_ids": [
                permission_ids["projects:connect"],
                permission_ids["projects:read"],
            ]
        },
        headers=root_headers,
    )
    alice_id = client.post(
        "/admin/users",
        json={
            "username": "alice",
            "password": "correct horse battery",
            "role_ids": [role_id],
        },
        headers=root_headers,
    ).json()["user_id"]
    alice_token = client.post(
        "/auth/login", json={"username": "alice", "password": "correct horse battery"}
    ).json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    project_root = tmp_path / "demo-project"
    project_root.mkdir()
    register_response = client.post(
        "/projects",
        json={"project_root": str(project_root)},
        headers=alice_headers,
    )
    assert register_response.status_code == 200
    assert register_response.json()["connected_by_user_id"] == alice_id
    project_id = register_response.json()["project_id"]

    # A non-admin (even one with projects:read) cannot reach the admin directory.
    assert (
        client.get(
            "/admin/projects",
            params={"database_url": database_url},
            headers=alice_headers,
        ).status_code
        == 403
    )

    admin_projects_response = client.get(
        "/admin/projects",
        params={"database_url": database_url},
        headers=root_headers,
    )
    assert admin_projects_response.status_code == 200
    listed = next(
        p
        for p in admin_projects_response.json()["projects"]
        if p["project_id"] == project_id
    )
    assert listed["connected_user_ids"] == [alice_id]
    assert "capabilities" in listed

    me_projects_response = client.get("/me/projects", headers=alice_headers)
    assert me_projects_response.status_code == 200
    assert [p["project_id"] for p in me_projects_response.json()["projects"]] == [
        project_id
    ]


def test_api_me_requires_authentication_even_when_enforcement_is_off(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("ORCHAI_AUTH_ENFORCED", raising=False)
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    client = TestClient(app)

    # Unlike every `require_permission`-gated route, `/me` never no-ops:
    # there is no meaningful "no-op" reading of "show my own profile".
    assert client.get("/me").status_code == 401
    assert (
        client.get("/providers/settings").status_code == 200
    )  # sanity: enforcement really is off


def test_api_me_show_update_and_projects(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity.db'}"
    monkeypatch.setenv("ORCHAI_DATABASE_URL", database_url)
    monkeypatch.setenv("ORCHAI_AUTH_SECRET_KEY", _TEST_SECRET_KEY)
    monkeypatch.setenv("ORCHAI_AUTH_ENFORCED", "true")
    _create_user(username="root", password="correct horse battery", is_superuser=True)
    client = TestClient(app)
    root_token = client.post(
        "/auth/login", json={"username": "root", "password": "correct horse battery"}
    ).json()["access_token"]
    root_headers = {"Authorization": f"Bearer {root_token}"}

    role_id = client.post(
        "/admin/access-roles", json={"name": "Basic"}, headers=root_headers
    ).json()["role_id"]
    client.post(
        "/admin/users",
        json={
            "username": "alice",
            "password": "correct horse battery",
            "role_ids": [role_id],
        },
        headers=root_headers,
    )
    alice_token = client.post(
        "/auth/login", json={"username": "alice", "password": "correct horse battery"}
    ).json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    show_response = client.get("/me", headers=alice_headers)
    assert show_response.status_code == 200
    assert show_response.json()["username"] == "alice"
    assert show_response.json()["access_roles"] == [
        {"role_id": role_id, "name": "Basic"}
    ]
    assert "password_hash" not in show_response.json()

    update_response = client.patch(
        "/me", json={"email": "alice@example.com"}, headers=alice_headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["email"] == "alice@example.com"
    # Never exposes a way to change one's own access roles or superuser flag.
    forbidden_field_response = client.patch(
        "/me", json={"is_superuser": True}, headers=alice_headers
    )
    assert forbidden_field_response.status_code == 422  # extra="forbid"

    # Renaming to another existing user's username is rejected.
    duplicate_username_response = client.patch(
        "/me", json={"username": "root"}, headers=alice_headers
    )
    assert duplicate_username_response.status_code == 409

    projects_response = client.get("/me/projects", headers=alice_headers)
    assert projects_response.status_code == 200
    assert projects_response.json() == {"projects": [], "count": 0}
