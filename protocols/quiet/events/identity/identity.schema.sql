-- Our own identities (local-only)
CREATE TABLE IF NOT EXISTS identities (
    identity_id TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    private_key BLOB NOT NULL,
    public_key BLOB NOT NULL,
    created_at INTEGER NOT NULL,
    name TEXT
);