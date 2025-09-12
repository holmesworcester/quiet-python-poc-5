-- Events table for storing all events
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    network_id TEXT,
    created_at INTEGER NOT NULL,
    peer_id TEXT,
    event_data TEXT NOT NULL,  -- JSON of event plaintext
    raw_bytes BLOB NOT NULL,   -- Raw event bytes (for encrypted events)
    validated_at INTEGER NOT NULL
);

-- Index for querying events by type and network
CREATE INDEX IF NOT EXISTS idx_events_type_network ON events(event_type, network_id);

-- Index for querying events by peer
CREATE INDEX IF NOT EXISTS idx_events_peer ON events(peer_id);

-- Index for querying events by creation time
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);