-- Combined schema for resolve_deps handler (includes unblocking logic)
-- Tracks blocked events waiting on dependencies and their resolution

CREATE TABLE IF NOT EXISTS blocked_events (
    event_id TEXT PRIMARY KEY,
    envelope_json TEXT NOT NULL,  -- Serialized envelope JSON
    created_at INTEGER NOT NULL,
    missing_deps TEXT NOT NULL,   -- JSON array of missing dependency IDs
    retry_count INTEGER DEFAULT 0 -- Track retries to prevent infinite loops
);

CREATE INDEX IF NOT EXISTS idx_blocked_events_created ON blocked_events(created_at);

-- Table to efficiently look up which events are waiting for a specific dependency
CREATE TABLE IF NOT EXISTS blocked_event_deps (
    event_id TEXT NOT NULL,
    dep_id TEXT NOT NULL,
    PRIMARY KEY (dep_id, event_id),
    FOREIGN KEY (event_id) REFERENCES blocked_events(event_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_blocked_event_deps_event ON blocked_event_deps(event_id);