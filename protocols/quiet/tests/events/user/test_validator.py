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
        event_data = valid_user_event["event_data"]
        metadata = valid_user_event["metadata"]
        
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_missing_required_fields(self, valid_user_event):
        """Test that missing required fields fail validation."""
        metadata = valid_user_event["metadata"]
        required_fields = ['type', 'user_id', 'peer_id', 'network_id', 'address', 'port', 'created_at', 'signature']
        
        for field in required_fields:
            event_data = valid_user_event["event_data"].copy()
            del event_data[field]
            assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_wrong_type(self, valid_user_event):
        """Test that wrong event type fails validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        event_data["type"] = "not_user"
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_peer_id_mismatch(self, valid_user_event):
        """Test that peer_id must match between event and metadata."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"].copy()
        
        # Change peer_id in event to not match metadata
        event_data["peer_id"] = "b" * 64
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_invalid_port(self, valid_user_event):
        """Test that invalid port numbers fail validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        # Port too low
        event_data["port"] = 0
        assert validate(event_data, metadata) == False
        
        # Port too high
        event_data["port"] = 65536
        assert validate(event_data, metadata) == False
        
        # Port as string
        event_data["port"] = "8080"
        assert validate(event_data, metadata) == False
        
        # Negative port
        event_data["port"] = -1
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_valid_ports(self, valid_user_event):
        """Test that valid port numbers pass validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        # Valid port boundaries
        for port in [1, 80, 443, 8080, 65535]:
            event_data["port"] = port
            assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_empty_address(self, valid_user_event):
        """Test that empty address fails validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        # Empty string
        event_data["address"] = ""
        assert validate(event_data, metadata) == False
        
        # Non-string
        event_data["address"] = 123
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_valid_addresses(self, valid_user_event):
        """Test that various address formats pass validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        valid_addresses = [
            "0.0.0.0",  # Placeholder
            "192.168.1.1",  # IPv4
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",  # IPv6
            "example.com",  # Hostname
            "localhost"  # Local
        ]
        
        for address in valid_addresses:
            event_data["address"] = address
            assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_empty_network_id(self, valid_user_event):
        """Test that empty network_id fails validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        event_data["network_id"] = ""
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_missing_metadata(self, valid_user_event):
        """Test validation with missing metadata."""
        event_data = valid_user_event["event_data"]
        
        # No metadata means no peer_id to check against
        assert validate(event_data, {}) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_user_extra_fields(self, valid_user_event):
        """Test that extra fields don't break validation."""
        event_data = valid_user_event["event_data"].copy()
        metadata = valid_user_event["metadata"]
        
        # Add extra fields
        event_data["extra_field"] = "some value"
        event_data["protocol_version"] = 2
        
        assert validate(event_data, metadata) == True