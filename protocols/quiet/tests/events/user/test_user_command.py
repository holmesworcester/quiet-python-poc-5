"""
Tests for user event type command (create).
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

from protocols.quiet.events.user.commands import create_user
from protocols.quiet.events.identity.commands import create_identity
from core.processor import process_envelope


class TestUserCommand:
    """Test user creation command."""
    
    @pytest.fixture
    def setup_identity(self, initialized_db):
        """Create identity for user tests."""
        # Create identity
        identity_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        process_envelope(identity_envelopes[0], initialized_db)
        identity_id = identity_envelopes[0]["event_plaintext"]["peer_id"]
        
        return identity_id
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_basic(self, initialized_db, setup_identity):
        """Test basic user creation."""
        identity_id = setup_identity
        
        params = {
            "identity_id": identity_id,
            "address": "192.168.1.100",
            "port": 8080
        }
        
        envelopes = create_user(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
        assert envelope["event_type"] == "user"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_id
        assert envelope["network_id"] == "test-network"
        assert envelope["deps"] == [f"identity:{identity_id}"]
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "user"
        assert event["peer_id"] == identity_id
        assert event["network_id"] == "test-network"
        assert event["address"] == "192.168.1.100"
        assert event["port"] == 8080
        assert "user_id" in event
        assert "created_at" in event
        assert event["signature"] == ""  # Unsigned at creation
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_defaults(self, initialized_db, setup_identity):
        """Test user creation with default address/port."""
        identity_id = setup_identity
        
        params = {
            "identity_id": identity_id
        }
        
        envelopes = create_user(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        # Should use default placeholder values
        assert event["address"] == "0.0.0.0"
        assert event["port"] == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_missing_identity(self, initialized_db):
        """Test that missing identity_id raises error."""
        params = {
            "address": "192.168.1.100",
            "port": 8080
        }
        
        with pytest.raises(ValueError, match="identity_id is required"):
            create_user(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_invalid_identity(self, initialized_db):
        """Test that invalid identity raises error."""
        params = {
            "identity_id": "non-existent-identity",
            "address": "192.168.1.100",
            "port": 8080
        }
        
        with pytest.raises(ValueError, match="Identity not found"):
            create_user(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_deterministic_id(self, initialized_db, setup_identity):
        """Test that user ID is deterministic based on inputs."""
        identity_id = setup_identity
        
        params = {
            "identity_id": identity_id,
            "address": "192.168.1.100",
            "port": 8080
        }
        
        # Two users created at different times should have different IDs
        envelopes1 = create_user(params, initialized_db)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelopes2 = create_user(params, initialized_db)
        
        assert envelopes1[0]["event_plaintext"]["user_id"] != envelopes2[0]["event_plaintext"]["user_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_port_validation(self, initialized_db, setup_identity):
        """Test port number validation."""
        identity_id = setup_identity
        
        # Valid ports
        for port in [1, 80, 443, 8080, 65535]:
            params = {
                "identity_id": identity_id,
                "port": port
            }
            envelopes = create_user(params, initialized_db)
            assert envelopes[0]["event_plaintext"]["port"] == port
        
        # Port as string should be converted
        params = {
            "identity_id": identity_id,
            "port": "8080"
        }
        envelopes = create_user(params, initialized_db)
        assert envelopes[0]["event_plaintext"]["port"] == 8080
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_ipv6_address(self, initialized_db, setup_identity):
        """Test creating user with IPv6 address."""
        identity_id = setup_identity
        
        params = {
            "identity_id": identity_id,
            "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "port": 8080
        }
        
        envelopes = create_user(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        assert event["address"] == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_hostname_address(self, initialized_db, setup_identity):
        """Test creating user with hostname as address."""
        identity_id = setup_identity
        
        params = {
            "identity_id": identity_id,
            "address": "example.com",
            "port": 8080
        }
        
        envelopes = create_user(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        assert event["address"] == "example.com"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_dependencies(self, initialized_db, setup_identity):
        """Test that user event declares correct dependencies."""
        identity_id = setup_identity
        
        params = {
            "identity_id": identity_id
        }
        
        envelopes = create_user(params, initialized_db)
        
        # Should depend on identity existing
        assert envelopes[0]["deps"] == [f"identity:{identity_id}"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_timestamp(self, initialized_db, setup_identity):
        """Test that user event has valid timestamp."""
        identity_id = setup_identity
        
        before = int(time.time() * 1000)
        
        params = {
            "identity_id": identity_id
        }
        
        envelopes = create_user(params, initialized_db)
        created_at = envelopes[0]["event_plaintext"]["created_at"]
        
        after = int(time.time() * 1000)
        
        # Timestamp should be in valid range
        assert before <= created_at <= after