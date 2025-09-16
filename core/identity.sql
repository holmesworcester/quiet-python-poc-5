-- Core framework identity storage
-- This table is managed by the framework, not by protocols

CREATE TABLE IF NOT EXISTS core_identities (
    identity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    private_key BLOB NOT NULL,
    public_key BLOB NOT NULL,
    created_at INTEGER NOT NULL,
    -- Future extensions
    recovery_key BLOB,
    biometric_hash BLOB,
    device_id TEXT
);

-- Index for listing identities by creation time
CREATE INDEX IF NOT EXISTS idx_core_identities_created
ON core_identities(created_at DESC);