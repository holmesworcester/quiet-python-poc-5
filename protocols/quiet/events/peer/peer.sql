-- Peers table for storing peer (identity on device) information
CREATE TABLE IF NOT EXISTS peers (
    -- The peer ID (hash of peer event)
    peer_id TEXT PRIMARY KEY,

    -- The public key of the identity this peer represents
    public_key TEXT NOT NULL,

    -- The identity ID (hash of identity event)
    identity_id TEXT NOT NULL,

    -- When the peer was created
    created_at INTEGER NOT NULL
);

-- Index for looking up by identity_id
CREATE INDEX IF NOT EXISTS idx_peers_identity
ON peers(identity_id);