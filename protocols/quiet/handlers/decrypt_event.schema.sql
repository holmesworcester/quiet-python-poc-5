-- Event keys for event-layer decryption
CREATE TABLE IF NOT EXISTS event_keys (
    key_id TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    secret BLOB NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER
);