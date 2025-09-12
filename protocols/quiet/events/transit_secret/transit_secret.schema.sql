-- Tables for transit_secret event type

-- Track which peers have which transit keys
CREATE TABLE IF NOT EXISTS peer_transit_keys (
    transit_key_id TEXT PRIMARY KEY,
    peer_id TEXT NOT NULL,
    network_id TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

-- Indexes for peer_transit_keys  
CREATE INDEX IF NOT EXISTS idx_peer_transit_keys_peer ON peer_transit_keys(peer_id);
CREATE INDEX IF NOT EXISTS idx_peer_transit_keys_network ON peer_transit_keys(network_id);