ALTER TABLE projects ADD COLUMN observed_readiness_level TEXT NOT NULL DEFAULT 'LEVEL_0_CONNECTABLE';
ALTER TABLE projects ADD COLUMN observed_security_profile TEXT NOT NULL DEFAULT '{}';
