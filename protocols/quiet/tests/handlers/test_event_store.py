"""
Tests for event_store handler.
"""
import pytest
import time
from protocols.quiet.handlers.event_store import (
    filter_func, handler, purge_event
)
from .test_base import HandlerTestBase


class TestEventStoreHandler(HandlerTestBase):
    """Test the event_store handler."""
    
    def test_filter_accepts_write_flag(self):
        """Test filter accepts envelopes with write_to_store flag."""
        envelope = self.create_envelope(
            write_to_store=True,
            event_id="test"
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_no_write_flag(self):
        """Test filter rejects envelopes without write flag."""
        envelope = self.create_envelope(
            event_id="test"
        )
        assert filter_func(envelope) is False
    
    def test_handler_stores_event(self):
        """Test handler stores event data."""
        test_time = int(time.time() * 1000)
        envelope = self.create_envelope(
            write_to_store=True,
            event_id="new_event_123",
            event_type="message",
            event_ciphertext=b"encrypted_data",
            key_ref={"kind": "key", "id": "key_123"},
            received_at=test_time - 1000,
            origin_ip="192.168.1.1",
            origin_port=8080
        )
        
        result = handler(envelope, self.db)
        
        assert result['stored'] is True
        
        # Check database
        cursor = self.db.execute(
            "SELECT * FROM events WHERE event_id = ?",
            ("new_event_123",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['event_type'] == 'message'
        assert row['event_ciphertext'] == b"encrypted_data"
        assert row['received_at'] == test_time - 1000
        assert row['origin_ip'] == "192.168.1.1"
        assert row['origin_port'] == 8080
        assert row['purged'] == 0
    
    def test_handler_stores_key_event(self):
        """Test handler stores unsealed key event."""
        envelope = self.create_envelope(
            write_to_store=True,
            event_id="key_event_456",
            event_type="key",
            key_id="key_456",
            unsealed_secret=b"secret_key_data",
            group_id="group_789"
        )
        
        result = handler(envelope, self.db)
        
        assert result['stored'] is True
        
        # Check database
        cursor = self.db.execute(
            "SELECT * FROM events WHERE event_id = ?",
            ("key_event_456",)
        )
        row = cursor.fetchone()
        assert row['key_id'] == 'key_456'
        assert row['unsealed_secret'] == b"secret_key_data"
        assert row['group_id'] == 'group_789'
    
    def test_handler_requires_event_id(self):
        """Test handler requires event_id."""
        envelope = self.create_envelope(
            write_to_store=True
            # Missing event_id
        )
        
        result = handler(envelope, self.db)
        
        assert 'error' in result
        assert 'event_id' in result['error']
    
    def test_handler_deduplicates(self):
        """Test handler handles duplicate event_id."""
        # Store first time
        envelope = self.create_envelope(
            write_to_store=True,
            event_id="dup_event",
            event_type="test"
        )
        result1 = handler(envelope, self.db)
        assert result1['stored'] is True
        
        # Try to store again
        result2 = handler(envelope, self.db)
        assert result2['stored'] is True  # Still returns success
        
        # Check only one in database
        cursor = self.db.execute(
            "SELECT COUNT(*) as count FROM events WHERE event_id = ?",
            ("dup_event",)
        )
        assert cursor.fetchone()['count'] == 1
    
    def test_handler_rejects_purged_events(self):
        """Test handler rejects already purged events."""
        # First purge an event
        purge_event("purged_event", self.db, "test_purge")
        
        # Try to store it
        envelope = self.create_envelope(
            write_to_store=True,
            event_id="purged_event",
            event_type="test"
        )
        
        result = handler(envelope, self.db)
        
        assert 'error' in result
        assert 'purged' in result['error']
    
    def test_purge_event_marks_purged(self):
        """Test purge_event marks event as purged."""
        # First store an event
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, purged)
            VALUES (?, ?, ?, ?)
        """, ("to_purge", "test", int(time.time() * 1000), False))
        self.db.commit()
        
        # Purge it
        success = purge_event("to_purge", self.db, "validation_failed")
        assert success is True
        
        # Check it's marked purged
        cursor = self.db.execute(
            "SELECT * FROM events WHERE event_id = ?",
            ("to_purge",)
        )
        row = cursor.fetchone()
        assert row['purged'] == 1
        assert row['purged_reason'] == 'validation_failed'
        assert row['purged_at'] is not None
        assert row['ttl_expire_at'] is not None
        
        # Should be 7 days in future
        ttl_delta = row['ttl_expire_at'] - row['purged_at']
        assert ttl_delta == 7 * 24 * 60 * 60 * 1000  # 7 days in ms
    
    def test_purge_event_deletes_projections(self):
        """Test purge_event also deletes from projections."""
        # Insert test data
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS projected_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                projection_data TEXT,
                projected_at INTEGER
            )
        """)
        
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, purged)
            VALUES (?, ?, ?, ?)
        """, ("projected_event", "test", 1000, False))
        
        self.db.execute("""
            INSERT INTO projected_events (event_id, event_type, projection_data, projected_at)
            VALUES (?, ?, ?, ?)
        """, ("projected_event", "test", "{}", 1000))
        self.db.commit()
        
        # Purge the event
        purge_event("projected_event", self.db, "test")
        
        # Check projection was deleted
        cursor = self.db.execute(
            "SELECT COUNT(*) as count FROM projected_events WHERE event_id = ?",
            ("projected_event",)
        )
        assert cursor.fetchone()['count'] == 0
    
    def test_purge_event_handles_missing(self):
        """Test purge_event handles missing events gracefully."""
        # Try to purge non-existent event
        success = purge_event("does_not_exist", self.db, "test")
        
        # Should still succeed (idempotent)
        assert success is True