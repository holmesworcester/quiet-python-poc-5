-- Groups table for storing group information
CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    name TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    permissions TEXT NOT NULL DEFAULT '{}' -- JSON
);

-- Group members table
CREATE TABLE IF NOT EXISTS group_members (
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    joined_at INTEGER NOT NULL,
    PRIMARY KEY (group_id, user_id)
);