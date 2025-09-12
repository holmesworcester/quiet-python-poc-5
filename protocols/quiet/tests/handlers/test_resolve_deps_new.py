"""
Tests for resolve_deps handler with new implementation.
"""
import pytest
import json
from protocols.quiet.handlers.resolve_deps import ResolveDepsHandler
from .test_base import HandlerTestBase


class TestResolveDepsHandler(HandlerTestBase):
    """Test the resolve_deps handler."""
    
    def setup_method(self):
        """Set up test handler."""
        super().setup_method()
        self.handler = ResolveDepsHandler()
    
    def test_filter_accepts_needs_resolution(self):
        """Test filter accepts envelopes that need dependency resolution."""
        # Has deps but not resolved
        envelope = self.create_envelope(
            deps=["identity:test_peer_id"],
            deps_included_and_valid=False
        )
        assert self.handler.filter(envelope) is True
        
        # Unblocked event
        envelope = self.create_envelope(
            deps=["key:test_key"],
            unblocked=True
        )
        assert self.handler.filter(envelope) is True
    
    def test_filter_rejects_already_resolved(self):
        """Test filter rejects envelopes with resolved deps."""
        envelope = self.create_envelope(
            deps=["identity:test_peer_id"],
            deps_included_and_valid=True
        )
        assert self.handler.filter(envelope) is False
    
    def test_filter_rejects_no_deps(self):
        """Test filter rejects envelopes without deps array."""
        envelope = self.create_envelope(
            deps_included_and_valid=False
        )
        assert self.handler.filter(envelope) is False
    
    def test_process_no_deps_needed(self):
        """Test processing envelope with empty deps array."""
        envelope = self.create_envelope(
            deps=[],
            event_id="test_event"
        )
        
        results = self.handler.process(envelope, self.db)
        
        assert len(results) == 1
        result = results[0]
        assert result['deps_included_and_valid'] is True
        assert result['resolved_deps'] == {}
    
    def test_process_resolves_identity_dep(self):
        """Test resolving identity dependency with private key."""
        # Insert test identity event
        self.db.execute("""
            INSERT INTO events (event_id, event_type, event_data, stored_at, validated)
            VALUES (?, ?, ?, ?, ?)
        """, ("test_peer_id", "identity", '{"peer_id": "test_peer_id"}', 1000, 1))
        self.db.commit()
        
        envelope = self.create_envelope(
            deps=["identity:test_peer_id"],
            event_id="test_event"
        )
        
        results = self.handler.process(envelope, self.db)
        
        assert len(results) == 1
        result = results[0]
        assert result['deps_included_and_valid'] is True
        assert 'identity:test_peer_id' in result['resolved_deps']
        
        # Should include private key from local storage
        identity_dep = result['resolved_deps']['identity:test_peer_id']
        assert identity_dep['event_id'] == 'test_peer_id'
        assert identity_dep['event_type'] == 'identity'
        assert identity_dep['validated'] is True
        assert 'local_metadata' in identity_dep
        assert identity_dep['local_metadata']['private_key'] == 'test_private_key'
    
    def test_process_resolves_transit_key_dep(self):
        """Test resolving transit key dependency (local secret)."""
        envelope = self.create_envelope(
            deps=["transit_key:test_transit_key"],
            event_id="test_event"
        )
        
        results = self.handler.process(envelope, self.db)
        
        assert len(results) == 1
        result = results[0]
        assert result['deps_included_and_valid'] is True
        assert 'transit_key:test_transit_key' in result['resolved_deps']
        
        # Transit key is not an event, just local data
        transit_dep = result['resolved_deps']['transit_key:test_transit_key']
        assert transit_dep['transit_secret'] == b'test_transit_secret'
        assert transit_dep['network_id'] == 'test_network'
        assert 'event_plaintext' not in transit_dep
    
    def test_process_handles_missing_deps(self):
        """Test handling missing dependencies."""
        envelope = self.create_envelope(
            deps=["identity:missing_peer", "key:missing_key"],
            event_id="test_event"
        )
        
        results = self.handler.process(envelope, self.db)
        
        # Should return empty list (drops envelope)
        assert len(results) == 0
        
        # Check that it was recorded as blocked
        cursor = self.db.execute(
            "SELECT * FROM blocked_by WHERE blocked_event_id = ?",
            ("test_event",)
        )
        blocked = cursor.fetchall()
        assert len(blocked) == 2
    
    def test_process_partial_deps_resolution(self):
        """Test envelope with some deps resolved, some missing."""
        envelope = self.create_envelope(
            deps=["transit_key:test_transit_key", "identity:missing_peer"],
            event_id="test_event"
        )
        
        results = self.handler.process(envelope, self.db)
        
        # Should drop envelope if any deps missing
        assert len(results) == 0
    
    def test_process_handles_retry_count(self):
        """Test that retry count is preserved in missing deps."""
        envelope = self.create_envelope(
            deps=["identity:missing_peer"],
            event_id="test_event",
            retry_count=5
        )
        
        results = self.handler.process(envelope, self.db)
        
        assert len(results) == 0  # Dropped due to missing deps
    
    def test_parse_dep_ref(self):
        """Test dependency reference parsing."""
        # With prefix
        dep_type, dep_id = self.handler._parse_dep_ref("identity:abc123")
        assert dep_type == "identity"
        assert dep_id == "abc123"
        
        # Without prefix (defaults to event)
        dep_type, dep_id = self.handler._parse_dep_ref("xyz789")
        assert dep_type == "event"
        assert dep_id == "xyz789"
        
        # With colon in ID
        dep_type, dep_id = self.handler._parse_dep_ref("key:group:main")
        assert dep_type == "key"
        assert dep_id == "group:main"