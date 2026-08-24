CREATE TABLE project_connections (
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    connected_at TEXT NOT NULL,
    PRIMARY KEY (project_id, user_id)
);
