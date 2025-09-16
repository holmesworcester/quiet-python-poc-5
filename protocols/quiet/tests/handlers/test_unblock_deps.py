"""
Tests for unblock_deps handler.
"""
import pytest
import json
import time
from protocols.quiet.handlers.resolve_deps import filter_func, handler
from protocols.quiet.tests.handlers.test_base import HandlerTestBase


class TestUnblockDepsHandler(HandlerTestBase):
    """Test the unblock_deps handler."""
    
    def test_filter_accepts_validated(self):
        """Test filter accepts newly validated events."""
        envelope = self.create_envelope(
            validated=True,
            event_id="validated_event"
        )
        assert filter_func(envelope) is True
    
    def test_filter_accepts_missing_deps(self):
        """Test filter accepts events with missing dependencies."""
        envelope = self.create_envelope(
            missing_deps=True,
            event_id="blocked_event"
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_others(self):
        """Test filter rejects events without validated or missing_deps."""
        envelope = self.create_envelope(
            event_id="test"
        )
        assert filter_func(envelope) is False
    
    def test_handler_blocks_missing_deps(self):
        """Test handler blocks events with missing dependencies."""
        envelope = self.create_envelope(
            missing_deps=True,
            event_id="blocked_event_123",
            missing_deps_list=["identity:missing_peer", "key:missing_key"],
            retry_count=0
        )
        
        results = handler(envelope, self.db)
        # Missing deps lead to blocking with no emission
        assert len(results) == 0
        
        # Check database
        cursor = self.db.execute(
            "SELECT * FROM blocked_events WHERE event_id = ?",
            ("blocked_event_123",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['retry_count'] == 0
        missing = json.loads(row['missing_deps'])
        assert "identity:missing_peer" in missing
        assert "key:missing_key" in missing
        
        # Check dependency tracking
        cursor = self.db.execute(
            "SELECT dep_id FROM blocked_event_deps WHERE event_id = ? ORDER BY dep_id",
            ("blocked_event_123",)
        )
        deps = [row['dep_id'] for row in cursor]
        assert deps == ["missing_key", "missing_peer"]
    
    def test_handler_unblocks_when_deps_satisfied(self):
        """Test handler unblocks events when all dependencies arrive."""
        # First, block an event
        blocked_envelope = self.create_envelope(
            event_id="waiting_event",
            event_type="message",
            missing_deps_list=["identity:dep1", "key:dep2"],
            custom_field="preserved"
        )
        
        self.db.execute("""
            INSERT INTO blocked_events (event_id, envelope_json, created_at, missing_deps, retry_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "waiting_event",
            json.dumps(blocked_envelope),
            int(time.time() * 1000),
            json.dumps(["identity:dep1", "key:dep2"]),
            0
        ))
        
        self.db.execute("""
            INSERT INTO blocked_event_deps (event_id, dep_id) VALUES (?, ?)
        """, ("waiting_event", "dep1"))
        self.db.execute("""
            INSERT INTO blocked_event_deps (event_id, dep_id) VALUES (?, ?)
        """, ("waiting_event", "dep2"))
        
        # Store the dependencies as validated
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, purged)
            VALUES (?, ?, ?, ?)
        """, ("dep1", "identity", 1000, 0))
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, purged)
            VALUES (?, ?, ?, ?)
        """, ("dep2", "key", 1000, 0))
        self.db.commit()
        
        # Now validate dep2 which should unblock
        envelope = self.create_envelope(
            validated=True,
            event_id="dep2"
        )
        
        results = handler(envelope, self.db)
        # Should return the unblocked envelope only
        assert len(results) == 1
        unblocked = results[0]
        assert unblocked['event_id'] == 'waiting_event'
        assert unblocked['unblocked'] is True
        assert unblocked['retry_count'] == 1
        assert unblocked['custom_field'] == 'preserved'
        
        # Should be removed from blocked_events
        cursor = self.db.execute(
            "SELECT COUNT(*) as count FROM blocked_events WHERE event_id = ?",
            ("waiting_event",)
        )
        assert cursor.fetchone()['count'] == 0
    
    def test_handler_only_unblocks_all_satisfied(self):
        """Test handler only unblocks when ALL dependencies satisfied."""
        # Block an event with two deps
        blocked_envelope = self.create_envelope(
            event_id="partial_deps",
            missing_deps_list=["identity:dep1", "key:dep2"]
        )
        
        self.db.execute("""
            INSERT INTO blocked_events (event_id, envelope_json, created_at, missing_deps, retry_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "partial_deps",
            json.dumps(blocked_envelope),
            1000,
            json.dumps(["identity:dep1", "key:dep2"]),
            0
        ))
        
        self.db.execute("""
            INSERT INTO blocked_event_deps (event_id, dep_id) VALUES (?, ?), (?, ?)
        """, ("partial_deps", "dep1", "partial_deps", "dep2"))
        
        # Only store dep1
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, purged)
            VALUES (?, ?, ?, ?)
        """, ("dep1", "identity", 1000, 0))
        self.db.commit()
        
        # Validate dep1
        envelope = self.create_envelope(
            validated=True,
            event_id="dep1"
        )
        
        results = handler(envelope, self.db)
        
        # Should NOT unblock (dep2 still missing) and no emission from handler
        assert len(results) == 0
        
        # Should still be blocked
        cursor = self.db.execute(
            "SELECT COUNT(*) as count FROM blocked_events WHERE event_id = ?",
            ("partial_deps",)
        )
        assert cursor.fetchone()['count'] == 1
    
    def test_handler_respects_retry_limit(self):
        """Test handler drops events exceeding retry limit."""
        # Block an event at retry limit
        blocked_envelope = self.create_envelope(
            event_id="max_retries",
            missing_deps_list=["identity:dep1"]
        )
        
        self.db.execute("""
            INSERT INTO blocked_events (event_id, envelope_json, created_at, missing_deps, retry_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "max_retries",
            json.dumps(blocked_envelope),
            1000,
            json.dumps(["identity:dep1"]),
            100  # At limit
        ))
        
        self.db.execute("""
            INSERT INTO blocked_event_deps (event_id, dep_id) VALUES (?, ?)
        """, ("max_retries", "dep1"))
        
        # Store the dependency
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, purged)
            VALUES (?, ?, ?, ?)
        """, ("dep1", "identity", 1000, 0))
        self.db.commit()
        
        # Validate dep1
        envelope = self.create_envelope(
            validated=True,
            event_id="dep1"
        )
        
        results = handler(envelope, self.db)
        
        # Should NOT unblock (exceeded retry limit) and no emission
        assert len(results) == 0
        
        # Should be removed from blocked_events
        cursor = self.db.execute(
            "SELECT COUNT(*) as count FROM blocked_events WHERE event_id = ?",
            ("max_retries",)
        )
        assert cursor.fetchone()['count'] == 0
    
    def test_handler_blocks_under_retry_limit(self):
        """Test handler blocks events under retry limit."""
        envelope = self.create_envelope(
            missing_deps=True,
            event_id="under_limit",
            missing_deps_list=["key:dep1"],
            retry_count=99  # Under 100 limit
        )
        
        results = handler(envelope, self.db)
        # Missing deps lead to blocking with no emission
        assert len(results) == 0
        
        # Should be blocked
        cursor = self.db.execute(
            "SELECT retry_count FROM blocked_events WHERE event_id = ?",
            ("under_limit",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['retry_count'] == 99
    
    def test_handler_extracts_event_id_from_deps(self):
        """Test handler correctly extracts event IDs from dep references."""
        # Block with complex dep references
        blocked_envelope = self.create_envelope(
            event_id="complex_deps",
            missing_deps_list=["identity:user:123", "key:group:main:456"]
        )
        
        self.db.execute("""
            INSERT INTO blocked_events (event_id, envelope_json, created_at, missing_deps, retry_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "complex_deps",
            json.dumps(blocked_envelope),
            1000,
            json.dumps(["identity:user:123", "key:group:main:456"]),
            0
        ))
        self.db.commit()
        
        # Process to store deps
        envelope = self.create_envelope(
            missing_deps=True,
            event_id="complex_deps",
            missing_deps_list=["identity:user:123", "key:group:main:456"]
        )
        
        handler(envelope, self.db)
        
        # Check stored dependency IDs
        cursor = self.db.execute(
            "SELECT dep_id FROM blocked_event_deps WHERE event_id = ? ORDER BY dep_id",
            ("complex_deps",)
        )
        deps = [row['dep_id'] for row in cursor]
        # Blocked dep ids are stored without prefixes in current schema
        assert deps == ["123", "456"]
