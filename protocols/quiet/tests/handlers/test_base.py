"""
Base test class for handler tests.
"""
import sqlite3
import tempfile
import os
from typing import Dict, Any, List
# Removed core.types import


class HandlerTestBase:
    """Base class for handler tests with common setup."""
    
    def setup_method(self):
        """Set up test database and common fixtures."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        
        # Create common tables
        self._create_tables()
        
        # Insert test data
        self._insert_test_data()
    
    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def _create_tables(self):
        """Create common tables needed by handlers."""
        # Events table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                event_ciphertext BLOB,
                event_key_id TEXT,
                key_id TEXT,
                unsealed_secret BLOB,
                group_id TEXT,
                received_at INTEGER,
                origin_ip TEXT,
                origin_port INTEGER,
                stored_at INTEGER NOT NULL,
                purged BOOLEAN DEFAULT FALSE,
                purged_at INTEGER,
                purged_reason TEXT,
                ttl_expire_at INTEGER,
                validated BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Transit keys table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS transit_keys (
                transit_key_id TEXT PRIMARY KEY,
                transit_secret BLOB NOT NULL,
                network_id TEXT NOT NULL
            )
        """)
        
        # Signing keys table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS signing_keys (
                peer_id TEXT PRIMARY KEY,
                private_key TEXT NOT NULL
            )
        """)
        
        # Blocked events table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_events (
                event_id TEXT PRIMARY KEY,
                envelope_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                missing_deps TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        # Blocked event dependencies
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_event_deps (
                event_id TEXT NOT NULL,
                dep_id TEXT NOT NULL,
                PRIMARY KEY (dep_id, event_id)
            )
        """)
        
        # Deleted events
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS deleted_events (
                event_id TEXT PRIMARY KEY,
                deleted_at INTEGER NOT NULL,
                deleted_by TEXT,
                reason TEXT
            )
        """)

        # Deleted channels
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS deleted_channels (
                channel_id TEXT PRIMARY KEY,
                deleted_at INTEGER NOT NULL
            )
        """)

        self.db.commit()
    
    def _insert_test_data(self):
        """Insert common test data."""
        # Test transit key
        self.db.execute("""
            INSERT INTO transit_keys (transit_key_id, transit_secret, network_id)
            VALUES (?, ?, ?)
        """, ("test_transit_key", b"test_transit_secret", "test_network"))
        
        # Test identity with private key
        self.db.execute("""
            INSERT INTO signing_keys (peer_id, private_key)
            VALUES (?, ?)
        """, ("test_peer_id", "test_private_key"))
        
        # Test validated event
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, validated)
            VALUES (?, ?, ?, ?)
        """, ("test_event_id", "test", 1000, True))
        
        self.db.commit()
    
    def create_envelope(self, **kwargs: Any) -> dict[str, Any]:
        """Create a test envelope with given fields."""
        envelope: dict[str, Any] = {}
        envelope.update(kwargs)
        return envelope