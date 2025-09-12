"""
Tests for identity event type validator.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.identity.validator import validate


class TestIdentityValidator:
    """Test identity event validation."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_identity_event(self, sample_identity_event):
        """Test that a valid identity event passes validation."""
        envelope = {"event_plaintext": sample_identity_event, "event_type": "identity"}
        assert validate(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_type(self, sample_identity_event):
        """Test that identity without type field fails."""
        event = sample_identity_event.copy()
        del event["type"]
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_wrong_type(self, sample_identity_event):
        """Test that identity with wrong type fails."""
        event = sample_identity_event.copy()
        event["type"] = "wrong_type"
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_peer_id(self, sample_identity_event):
        """Test that identity without peer_id fails."""
        event = sample_identity_event.copy()
        del event["peer_id"]
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_signature(self, sample_identity_event):
        """Test that identity without signature fails."""
        event = sample_identity_event.copy()
        del event["signature"]
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_invalid_signature(self, sample_identity_event):
        """Test that identity with invalid signature still passes structural validation."""
        event = sample_identity_event.copy()
        # Corrupt the signature - validator doesn't check signature validity
        event["signature"] = "0" * 128
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        assert validate(envelope) == True  # Validators only check structure
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_tampered_event(self, sample_identity_event):
        """Test that tampered identity event still passes structural validation."""
        event = sample_identity_event.copy()
        # Change content after signing - validator doesn't check signature validity
        event["network_id"] = "tampered-network"
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        assert validate(envelope) == True  # Validators only check structure
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_invalid_peer_id_hex(self, sample_identity_event):
        """Test that identity with invalid peer_id hex fails."""
        event = sample_identity_event.copy()
        event["peer_id"] = "not-valid-hex"
        
        envelope = {"event_plaintext": event, "event_type": "identity"}
        # This should return False (not raise)
        assert validate(envelope) == False