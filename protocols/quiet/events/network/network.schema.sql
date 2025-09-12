-- Networks table for storing network information
CREATE TABLE IF NOT EXISTS networks (
    network_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    creator_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);