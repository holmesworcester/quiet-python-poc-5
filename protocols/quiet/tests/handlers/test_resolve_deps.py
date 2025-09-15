"""
Tests for resolve_deps handler.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
protocol_dir = Path(__file__).parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.handlers.resolve_deps import filter_func, handler


class TestResolveDepsHandler:
    """Test dependency resolution handler."""

    @pytest.fixture
    def resolve_filter(self):
        """Get filter function."""
        return filter_func
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_no_deps_included_and_valid(self, resolve_filter):
        """Test filter matches envelopes without deps_included_and_valid."""
        envelope = {
            "event_type": "test",
            "event_plaintext": {"type": "test"}
        }
        assert resolve_filter(envelope) == True
        
        envelope_with_false = {
            "event_type": "test", 
            "event_plaintext": {"type": "test"},
            "deps_included_and_valid": False
        }
        assert resolve_filter(envelope_with_false) == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_with_deps_valid(self, resolve_filter):
        """Test filter rejects envelopes with deps already valid."""
        envelope = {
            "event_type": "test",
            "event_plaintext": {"type": "test"},
            "deps_included_and_valid": True
        }
        assert resolve_filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_unblocked(self, resolve_filter):
        """Test filter matches unblocked envelopes."""
        envelope = {
            "event_type": "test",
            "event_plaintext": {"type": "test"},
            "deps_included_and_valid": True,
            "unblocked": True
        }
        assert resolve_filter(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_identity_no_deps(self, resolve_filter, sample_identity_event, initialized_db):
        """Test processing identity event with no dependencies."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "peer_id": sample_identity_event["peer_id"]
        }
        
        results = handler(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as deps valid with no missing deps
        assert result["deps_included_and_valid"] == True
        assert result["missing_deps"] == []
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_key_with_missing_peer_dep(self, handler, sample_key_event, initialized_db):
        """Test processing key event with missing peer dependency."""
        envelope = {
            "event_plaintext": sample_key_event,
            "event_type": "key"
        }
        
        results = handler(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should have missing peer dependency
        assert result["deps_included_and_valid"] == False
        assert len(result["missing_deps"]) > 0
        assert sample_key_event["created_by"] in result["missing_deps"]
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_key_with_resolved_peer_dep(self, handler, sample_key_event, sample_identity_event, initialized_db):
        """Test processing key event with resolved peer dependency."""
        # First store the identity as validated
        cursor = initialized_db.cursor()
        cursor.execute("""
            INSERT INTO validated_events (event_id, event_plaintext, event_type, validated_at)
            VALUES (?, ?, ?, ?)
        """, (
            sample_identity_event["peer_id"],
            str(sample_identity_event),
            "identity",
            1000
        ))
        initialized_db.commit()
        
        # Now process key event
        envelope = {
            "event_plaintext": sample_key_event,
            "event_type": "key"
        }
        
        results = handler(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should have resolved the dependency
        assert result["deps_included_and_valid"] == True
        assert result["missing_deps"] == []
        assert "included_deps" in result
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_preserves_envelope(self, handler, sample_identity_event, initialized_db):
        """Test that handler preserves original envelope data."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "peer_id": sample_identity_event["peer_id"],
            "custom_field": "preserved"
        }
        
        results = handler(envelope, initialized_db)
        result = results[0]
        
        # Original fields should be preserved
        assert result["event_plaintext"] == sample_identity_event
        assert result["event_type"] == "identity"
        assert result["peer_id"] == sample_identity_event["peer_id"]
        assert result["custom_field"] == "preserved"