-- Schema for resolve_deps handler
-- Tracks blocked events and their dependencies

CREATE TABLE IF NOT EXISTS blocked_events (
    event_id TEXT PRIMARY KEY,
    envelope_data TEXT NOT NULL,  -- Serialized envelope
    missing_deps TEXT NOT NULL,   -- JSON array of missing dep IDs
    retry_count INTEGER DEFAULT 0,
    blocked_at INTEGER NOT NULL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS blocked_by (
    blocked_event_id TEXT NOT NULL,
    blocking_event_id TEXT NOT NULL,
    PRIMARY KEY (blocked_event_id, blocking_event_id)
);

CREATE INDEX IF NOT EXISTS idx_blocked_by_blocking ON blocked_by(blocking_event_id);