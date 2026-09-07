CREATE TABLE automatic_policy (
    id TEXT PRIMARY KEY,
    allowed_operations TEXT NOT NULL,
    allowed_cross_role_transitions TEXT NOT NULL,
    allow_model_substitution INTEGER NOT NULL,
    allow_context_expansion INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
