-- Events table for storing all events and managing purged events
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT,
    event_ciphertext BLOB,
    event_key_id TEXT,
    
    -- Key event fields
    key_id TEXT,
    unsealed_secret BLOB,
    group_id TEXT,
    
    -- Network metadata
    received_at INTEGER,
    origin_ip TEXT,
    origin_port INTEGER,
    stored_at INTEGER NOT NULL,
    
    -- Purge tracking
    purged BOOLEAN DEFAULT FALSE,
    purged_at INTEGER,
    purged_reason TEXT,
    ttl_expire_at INTEGER  -- When to clean up purged events
);

-- Index for querying events by type
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- Index for querying events by key_id
CREATE INDEX IF NOT EXISTS idx_events_key ON events(event_key_id);

-- Index for purged events and TTL cleanup
CREATE INDEX IF NOT EXISTS idx_events_purged ON events(purged, ttl_expire_at);

-- Index for received time (for observability)
CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);

-- Projected events table (for event type specific projections)
CREATE TABLE IF NOT EXISTS projected_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    projection_data TEXT NOT NULL,  -- JSON of projected data
    projected_at INTEGER NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(event_id)
);