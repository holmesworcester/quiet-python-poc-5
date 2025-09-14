"""
Tests for key event type validator.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.key.validator import validate
from core.crypto import generate_keypair, sign


class TestKeyValidator:
    """Test key event validation."""
    
    @pytest.fixture
    def valid_key_event(self, test_identity):
        """Create a valid key event for testing."""
        import json
        import time
        
        event = {
            "type": "key",
            "key_id": "0" * 64,  # 32 bytes hex
            "group_id": "test-group",
            "sealed_key": "0" * 128,  # Mock sealed key (64 bytes hex)
            "peer_id": test_identity["peer_id"],
            "network_id": test_identity["network_id"],
            "created_at": int(time.time() * 1000)
        }
        
        # Sign the event
        message = json.dumps(event, sort_keys=True).encode()
        signature = sign(message, test_identity["private_key"])
        event["signature"] = signature.hex()
        
        return event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_key_event(self, valid_key_event):
        """Test that a valid key event passes validation."""
        envelope = {"event_plaintext": valid_key_event, "event_type": "key"}
        assert validate(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_type(self, valid_key_event):
        """Test that key without type field fails."""
        event = valid_key_event.copy()
        del event["type"]
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_wrong_type(self, valid_key_event):
        """Test that key with wrong type fails."""
        event = valid_key_event.copy()
        event["type"] = "wrong_type"
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_key_id(self, valid_key_event):
        """Test that key without key_id fails."""
        event = valid_key_event.copy()
        del event["key_id"]
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_group_id(self, valid_key_event):
        """Test that key without group_id fails."""
        event = valid_key_event.copy()
        del event["group_id"]
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_sealed_key(self, valid_key_event):
        """Test that key without sealed_key fails."""
        event = valid_key_event.copy()
        del event["sealed_key"]
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_peer_id(self, valid_key_event):
        """Test that key without peer_id fails."""
        event = valid_key_event.copy()
        del event["peer_id"]
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_signature(self, valid_key_event):
        """Test that key without signature fails."""
        event = valid_key_event.copy()
        del event["signature"]
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_invalid_signature(self, valid_key_event):
        """Test that key with invalid signature still passes structural validation."""
        event = valid_key_event.copy()
        # Corrupt the signature - validator doesn't check signature validity
        event["signature"] = "0" * 128
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == True  # Validators only check structure
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_tampered_event(self, valid_key_event):
        """Test that tampered key event still passes structural validation."""
        event = valid_key_event.copy()
        # Change content after signing - validator doesn't check signature validity
        event["group_id"] = "tampered-group"
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == True  # Validators only check structure
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_different_signer(self, valid_key_event):
        """Test that key signed by different identity still passes structural validation."""
        event = valid_key_event.copy()
        # Change peer_id after signing - validator doesn't check signature validity
        event["peer_id"] = "a" * 64
        
        envelope = {"event_plaintext": event, "event_type": "key"}
        assert validate(envelope) == True  # Validators only check structure