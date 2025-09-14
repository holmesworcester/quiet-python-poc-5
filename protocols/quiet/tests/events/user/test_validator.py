"""
Tests for user event type validator.
"""
import pytest
import sys
import time
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.user.validator import validate


class TestUserValidator:
    """Test user event validation."""
    
    @pytest.fixture
    def valid_user_event(self):
        """Create a valid user event."""
        peer_id = "a" * 64  # Mock peer ID
        return {
            "event_data": {
                "type": "user",
                "user_id": "test-user-id",
                "peer_id": peer_id,
                "network_id": "test-network",
                "address": "192.168.1.100",
                "port": 8080,
                "created_at": int(time.time() * 1000),
                "signature": "test-signature"
            },
            "metadata": {
                "peer_id": peer_id
            }
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_user_event(self, valid_user_event):
        """Test validation of a valid user event."""
        envelope = {
            "event_plaintext": valid_user_event["event_data"],
            "peer_id": valid_user_event["metadata"]["peer_id"]
        }
        
        assert validate(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_missing_required_fields(self, valid_user_event):
        """Test that missing required fields fail validation."""
        peer_id = valid_user_event["metadata"]["peer_id"]
        required_fields = ['type', 'user_id', 'peer_id', 'network_id', 'address', 'port', 'created_at', 'signature']
        
        for field in required_fields:
            event_data = valid_user_event["event_data"].copy()
            del event_data[field]
            envelope = {"event_plaintext": event_data, "peer_id": peer_id}
            assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_wrong_type(self, valid_user_event):
        """Test that wrong event type fails validation."""
        event_data = valid_user_event["event_data"].copy()
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        event_data["type"] = "not_user"
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_peer_id_mismatch(self, valid_user_event):
        """Test that peer_id must match between event and envelope."""
        event_data = valid_user_event["event_data"].copy()
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        # Change peer_id in event to not match envelope
        event_data["peer_id"] = "b" * 64
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_invalid_port(self, valid_user_event):
        """Test that invalid port numbers fail validation."""
        event_data = valid_user_event["event_data"].copy()
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        # Port too low
        event_data["port"] = 0
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
        
        # Port too high
        event_data["port"] = 65536
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
        
        # Port as string
        event_data["port"] = "8080"
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
        
        # Negative port
        event_data["port"] = -1
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_valid_ports(self, valid_user_event):
        """Test that valid port numbers pass validation."""
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        # Valid port boundaries
        for port in [1, 80, 443, 8080, 65535]:
            event_data = valid_user_event["event_data"].copy()
            event_data["port"] = port
            envelope = {"event_plaintext": event_data, "peer_id": peer_id}
            assert validate(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_empty_address(self, valid_user_event):
        """Test that empty address fails validation."""
        event_data = valid_user_event["event_data"].copy()
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        # Empty string
        event_data["address"] = ""
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
        
        # Non-string
        event_data["address"] = 123
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_valid_addresses(self, valid_user_event):
        """Test that various address formats pass validation."""
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        valid_addresses = [
            "0.0.0.0",  # Placeholder
            "192.168.1.1",  # IPv4
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",  # IPv6
            "example.com",  # Hostname
            "localhost"  # Local
        ]
        
        for address in valid_addresses:
            event_data = valid_user_event["event_data"].copy()
            event_data["address"] = address
            envelope = {"event_plaintext": event_data, "peer_id": peer_id}
            assert validate(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_empty_network_id(self, valid_user_event):
        """Test that empty network_id fails validation."""
        event_data = valid_user_event["event_data"].copy()
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        event_data["network_id"] = ""
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_missing_peer_id(self, valid_user_event):
        """Test validation with missing peer_id."""
        event_data = valid_user_event["event_data"]
        
        # No peer_id in envelope
        envelope = {"event_plaintext": event_data}
        assert validate(envelope) == True  # Validation passes without peer_id check
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_extra_fields(self, valid_user_event):
        """Test that extra fields don't break validation."""
        event_data = valid_user_event["event_data"].copy()
        peer_id = valid_user_event["metadata"]["peer_id"]
        
        # Add extra fields
        event_data["extra_field"] = "some value"
        event_data["protocol_version"] = 2
        
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == True