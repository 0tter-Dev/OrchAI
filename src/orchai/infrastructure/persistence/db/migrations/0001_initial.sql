CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_location TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    capabilities TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    project_id TEXT,
    execution_mode TEXT NOT NULL,
    state TEXT NOT NULL,
    requested_change TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    constraints TEXT NOT NULL,
    exclusions TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE authorization_requests (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    model_id TEXT,
    context_scope TEXT NOT NULL,
    proposed_state TEXT,
    reason TEXT NOT NULL,
    requester TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE authorization_decisions (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    FOREIGN KEY(request_id) REFERENCES authorization_requests(id)
);

CREATE TABLE executions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    model_id TEXT NOT NULL,
    authorization_id TEXT NOT NULL,
    project_id TEXT,
    requested_context TEXT NOT NULL,
    authorized_context TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    state TEXT NOT NULL,
    result_output TEXT,
    result_success INTEGER,
    result_errors TEXT,
    result_warnings TEXT,
    result_resource_usage TEXT,
    result_metadata TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(authorization_id) REFERENCES authorization_requests(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

