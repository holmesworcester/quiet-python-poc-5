"""
Tests for transit_secret event type validator.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.event_types.transit_secret.validators.validate import validate
from core.crypto import generate_keypair, sign


class TestTransitSecretValidator:
    """Test transit secret event validation."""
    
    @pytest.fixture
    def valid_transit_secret_event(self, test_identity):
        """Create a valid transit secret event for testing."""
        import json
        import time
        
        event = {
            "type": "transit_secret",
            "transit_key_id": "test-transit-key-" + str(int(time.time())),
            "network_id": test_identity["network_id"],
            "peer_id": test_identity["peer_id"],
            "created_at": int(time.time() * 1000)
        }
        
        # Sign the event
        message = json.dumps(event, sort_keys=True).encode()
        signature = sign(message, test_identity["private_key"])
        event["signature"] = signature.hex()
        
        return event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_transit_secret_event(self, valid_transit_secret_event):
        """Test that a valid transit secret event passes validation."""
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(valid_transit_secret_event, envelope_metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_type(self, valid_transit_secret_event):
        """Test that transit secret without type field fails."""
        event = valid_transit_secret_event.copy()
        del event["type"]
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_wrong_type(self, valid_transit_secret_event):
        """Test that transit secret with wrong type fails."""
        event = valid_transit_secret_event.copy()
        event["type"] = "wrong_type"
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_transit_key_id(self, valid_transit_secret_event):
        """Test that transit secret without transit_key_id fails."""
        event = valid_transit_secret_event.copy()
        del event["transit_key_id"]
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_network_id(self, valid_transit_secret_event):
        """Test that transit secret without network_id fails."""
        event = valid_transit_secret_event.copy()
        del event["network_id"]
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_peer_id(self, valid_transit_secret_event):
        """Test that transit secret without peer_id fails."""
        event = valid_transit_secret_event.copy()
        del event["peer_id"]
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_missing_signature(self, valid_transit_secret_event):
        """Test that transit secret without signature fails."""
        event = valid_transit_secret_event.copy()
        del event["signature"]
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_invalid_signature(self, valid_transit_secret_event):
        """Test that transit secret with invalid signature fails."""
        event = valid_transit_secret_event.copy()
        # Corrupt the signature
        event["signature"] = "0" * 128
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_tampered_event(self, valid_transit_secret_event):
        """Test that tampered transit secret event fails validation."""
        event = valid_transit_secret_event.copy()
        # Change content after signing
        event["network_id"] = "tampered-network"
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(event, envelope_metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_no_secret_in_event(self, valid_transit_secret_event):
        """Test that transit secret event doesn't contain actual secret."""
        # Validator should pass even without secret field
        # (secrets are kept local only)
        assert "secret" not in valid_transit_secret_event
        assert "encrypted_secret" not in valid_transit_secret_event
        
        envelope_metadata = {"event_type": "transit_secret"}
        assert validate(valid_transit_secret_event, envelope_metadata) == True