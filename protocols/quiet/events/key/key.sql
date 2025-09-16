-- Tables for key event type

-- Track group encryption keys
CREATE TABLE IF NOT EXISTS group_keys (
    key_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    peer_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

-- Indexes for group_keys
CREATE INDEX IF NOT EXISTS idx_group_keys_group ON group_keys(group_id);
CREATE INDEX IF NOT EXISTS idx_group_keys_peer ON group_keys(peer_id);