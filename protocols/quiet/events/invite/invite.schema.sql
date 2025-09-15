-- Invites table for storing network invites
CREATE TABLE IF NOT EXISTS invites (
    invite_id TEXT PRIMARY KEY,
    invite_pubkey TEXT NOT NULL UNIQUE,
    invite_secret TEXT NOT NULL,
    network_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    inviter_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);