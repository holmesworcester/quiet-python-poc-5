-- Link-invite table for linking peers to user accounts
CREATE TABLE IF NOT EXISTS link_invites (
    -- The link ID (hash of link_invite event)
    link_id TEXT PRIMARY KEY,

    -- The peer being linked
    peer_id TEXT NOT NULL,

    -- The user account being linked to
    user_id TEXT NOT NULL,

    -- Network this link belongs to
    network_id TEXT NOT NULL,

    -- When the link was created
    created_at INTEGER NOT NULL,

    -- Ensure one link per peer-user pair
    UNIQUE(peer_id, user_id)
);

-- Index for querying links by peer
CREATE INDEX IF NOT EXISTS idx_link_invites_peer
ON link_invites(peer_id);

-- Index for querying links by user
CREATE INDEX IF NOT EXISTS idx_link_invites_user
ON link_invites(user_id);