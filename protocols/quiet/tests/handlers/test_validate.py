"""
Tests for validate handler.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
protocol_dir = Path(__file__).parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.handlers.validate.handler import ValidateHandler


class TestValidateHandler:
    """Test validation handler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return ValidateHandler()
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_requires_sig_checked(self, handler):
        """Test filter requires sig_checked to be true."""
        envelope = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
            "deps_included_and_valid": True
        }
        assert handler.filter(envelope) == False
        
        envelope["sig_checked"] = False
        assert handler.filter(envelope) == False
        
        envelope["sig_checked"] = True
        assert handler.filter(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_skips_validated(self, handler):
        """Test filter skips already validated envelopes."""
        envelope = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
            "deps_included_and_valid": True,
            "sig_checked": True,
            "validated": True
        }
        assert handler.filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_requires_event_plaintext(self, handler):
        """Test filter requires event_plaintext."""
        envelope = {
            "event_type": "identity",
            "deps_included_and_valid": True,
            "sig_checked": True
        }
        assert handler.filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_valid_identity(self, handler, sample_identity_event, initialized_db):
        """Test processing valid identity event."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "deps_included_and_valid": True,
            "sig_checked": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as validated
        assert result["validated"] == True
        assert "error" not in result
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_invalid_identity(self, handler, sample_identity_event, initialized_db):
        """Test processing invalid identity event."""
        # Remove required field
        event = sample_identity_event.copy()
        del event["peer_id"]
        
        envelope = {
            "event_plaintext": event,
            "event_type": "identity",
            "deps_included_and_valid": True,
            "sig_checked": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should not be validated
        assert result.get("validated") != True
        # Original envelope should be returned unchanged
        assert result["event_plaintext"] == event
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_stores_validated_event(self, handler, sample_identity_event, initialized_db):
        """Test that validated events are stored in database."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "deps_included_and_valid": True,
            "sig_checked": True,
            "peer_id": sample_identity_event["peer_id"]
        }
        
        results = handler.process(envelope, initialized_db)
        
        # Check database for validated event
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT * FROM validated_events WHERE event_id = ?",
            (sample_identity_event["peer_id"],)
        )
        
        row = cursor.fetchone()
        assert row is not None
        assert row["event_type"] == "identity"
        assert row["validated_at"] is not None
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_unknown_event_type(self, handler, initialized_db):
        """Test processing unknown event type."""
        envelope = {
            "event_plaintext": {"type": "unknown_type"},
            "event_type": "unknown_type",
            "deps_included_and_valid": True,
            "sig_checked": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should not be validated (no validator for unknown type)
        assert result.get("validated") != True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_preserves_envelope_data(self, handler, sample_identity_event, initialized_db):
        """Test that handler preserves all envelope data."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "deps_included_and_valid": True,
            "sig_checked": True,
            "custom_field": "preserved",
            "peer_id": sample_identity_event["peer_id"]
        }
        
        results = handler.process(envelope, initialized_db)
        result = results[0]
        
        # All fields should be preserved
        assert result["event_plaintext"] == sample_identity_event
        assert result["event_type"] == "identity"
        assert result["deps_included_and_valid"] == True
        assert result["sig_checked"] == True
        assert result["custom_field"] == "preserved"
        assert result["validated"] == True