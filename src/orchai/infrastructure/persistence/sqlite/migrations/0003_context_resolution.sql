CREATE TABLE context_resolution_records (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    source TEXT NOT NULL,
    resource TEXT NOT NULL,
    scope TEXT,
    version TEXT,
    content_sha256 TEXT NOT NULL,
    content_bytes INTEGER NOT NULL,
    resolved_at TEXT NOT NULL,
    metadata TEXT NOT NULL,
    FOREIGN KEY(execution_id) REFERENCES executions(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE INDEX idx_context_resolution_execution_id
    ON context_resolution_records(execution_id);
