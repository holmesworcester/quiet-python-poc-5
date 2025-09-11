"""
Database setup and utilities.
"""
import sqlite3
from typing import Optional
import os


def get_connection(db_path: str = "quiet.db") -> sqlite3.Connection:
    """Get a database connection with proper settings."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database(conn: sqlite3.Connection):
    """Initialize database schema."""
    
    # Events table - stores all validated events
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            network_id TEXT,
            created_at INTEGER NOT NULL,
            peer_id TEXT,
            event_data TEXT NOT NULL,  -- JSON
            raw_bytes BLOB NOT NULL,   -- Original 512 bytes
            validated_at INTEGER NOT NULL
        )
    """)
    
    # Blocked events waiting for dependencies
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocked_events (
            event_id TEXT PRIMARY KEY,
            envelope_data TEXT NOT NULL,  -- Serialized envelope
            missing_deps TEXT NOT NULL,   -- JSON array of missing dep IDs
            retry_count INTEGER DEFAULT 0,
            blocked_at INTEGER NOT NULL,
            reason TEXT
        )
    """)
    
    # Dependency tracking for unblocking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocked_by (
            blocked_event_id TEXT NOT NULL,
            blocking_event_id TEXT NOT NULL,
            PRIMARY KEY (blocked_event_id, blocking_event_id)
        )
    """)
    
    # Transit keys for decryption
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transit_keys (
            key_id TEXT PRIMARY KEY,
            network_id TEXT NOT NULL,
            secret BLOB NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER
        )
    """)
    
    # Event keys for event-layer decryption
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_keys (
            key_id TEXT PRIMARY KEY,
            network_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            secret BLOB NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER
        )
    """)
    
    # Peer information
    conn.execute("""
        CREATE TABLE IF NOT EXISTS peers (
            peer_id TEXT PRIMARY KEY,
            network_id TEXT NOT NULL,
            public_key BLOB NOT NULL,
            added_at INTEGER NOT NULL
        )
    """)
    
    # Our own identities
    conn.execute("""
        CREATE TABLE IF NOT EXISTS identities (
            identity_id TEXT PRIMARY KEY,
            network_id TEXT NOT NULL,
            private_key BLOB NOT NULL,
            public_key BLOB NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    
    # Outgoing queue
    conn.execute("""
        CREATE TABLE IF NOT EXISTS outgoing_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            envelope_data TEXT NOT NULL,
            due_ms INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    
    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_network ON events(network_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocked_by_blocking ON blocked_by(blocking_event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_outgoing_due ON outgoing_queue(due_ms)")
    
    conn.commit()