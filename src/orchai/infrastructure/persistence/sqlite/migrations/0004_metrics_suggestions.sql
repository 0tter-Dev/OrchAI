CREATE TABLE metric_records (
    id TEXT PRIMARY KEY,
    observed_at TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    task_id TEXT,
    project_id TEXT,
    execution_id TEXT,
    dimensions TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(execution_id) REFERENCES executions(id)
);

CREATE INDEX idx_metric_records_task_id ON metric_records(task_id);
CREATE INDEX idx_metric_records_name ON metric_records(name);
CREATE INDEX idx_metric_records_observed_at ON metric_records(observed_at);

CREATE TABLE suggestions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    related_execution_id TEXT,
    suggested_role TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    rationale TEXT NOT NULL,
    required_capabilities TEXT NOT NULL,
    expected_impact TEXT NOT NULL,
    authorization_required INTEGER NOT NULL,
    confidence REAL,
    status TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    metadata TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id),
    FOREIGN KEY(related_execution_id) REFERENCES executions(id)
);

CREATE INDEX idx_suggestions_task_id ON suggestions(task_id);
CREATE INDEX idx_suggestions_status ON suggestions(status);
