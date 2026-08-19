CREATE TABLE events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL,
    task_id TEXT,
    project_id TEXT,
    execution_id TEXT,
    correlation_id TEXT,
    causation_id TEXT,
    payload TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE INDEX idx_events_task_id ON events(task_id);
CREATE INDEX idx_events_occurred_at ON events(occurred_at);

CREATE TABLE audit_records (
    id TEXT PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    task_id TEXT,
    project_id TEXT,
    execution_id TEXT,
    authorization_id TEXT,
    event_id TEXT UNIQUE,
    correlation_id TEXT,
    causation_id TEXT,
    metadata TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(execution_id) REFERENCES executions(id),
    FOREIGN KEY(authorization_id) REFERENCES authorization_requests(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE INDEX idx_audit_records_task_id ON audit_records(task_id);
CREATE INDEX idx_audit_records_occurred_at ON audit_records(occurred_at);
