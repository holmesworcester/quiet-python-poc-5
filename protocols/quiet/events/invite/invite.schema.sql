-- Invites table for storing network invites
CREATE TABLE IF NOT EXISTS invites (
    invite_code TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    used INTEGER DEFAULT 0,
    used_by TEXT,
    used_at INTEGER
);