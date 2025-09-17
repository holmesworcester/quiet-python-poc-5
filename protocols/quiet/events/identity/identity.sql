-- Protocol-level identities table (local-only)
CREATE TABLE IF NOT EXISTS identities (
    identity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    public_key TEXT NOT NULL,
    private_key BLOB NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_identities_name
ON identities(name);

