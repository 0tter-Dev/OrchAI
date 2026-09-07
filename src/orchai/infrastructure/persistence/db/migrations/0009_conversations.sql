CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    project_id TEXT,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    archived INTEGER NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    provider_name TEXT NOT NULL,
    model_id TEXT,
    linked_task_id TEXT,
    linked_execution_id TEXT,
    resource_usage TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id),
    FOREIGN KEY(linked_task_id) REFERENCES tasks(id),
    FOREIGN KEY(linked_execution_id) REFERENCES executions(id)
);
