"""
Tests for user event type commands (create and join).
"""
import pytest
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.user.commands import create_user, join_as_user


class TestUserCommand:
    """Test user creation command."""
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_basic(self, initialized_db):
        """Test basic user creation."""
        identity_id = "test-identity-id"
        
        params = {
            "identity_id": identity_id,
            "address": "192.168.1.100",
            "port": 8080
        }
        
        envelope = create_user(params)
        
        # Should emit exactly one envelope
        # Single envelope returned

        assert envelope["event_type"] == "user"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_id
        assert envelope["network_id"] == ""
        assert envelope["deps"] == [f"identity:{identity_id}"]
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "user"
        assert event["peer_id"] == identity_id
        assert event["network_id"] == ""
        assert event["address"] == "192.168.1.100"
        assert event["port"] == 8080
        assert "user_id" in event
        assert "created_at" in event
        assert event["signature"] == ""  # Unsigned at creation
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_defaults(self, initialized_db):
        """Test user creation with default address/port."""
        identity_id = "test-identity-id"
        
        params = {
            "identity_id": identity_id
        }
        
        envelope = create_user(params)
        event = envelope["event_plaintext"]
        
        # Should use default placeholder values
        assert event["address"] == "0.0.0.0"
        assert event["port"] == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_missing_identity(self, initialized_db):
        """Test user creation with missing identity_id uses empty string."""
        params = {
            "address": "192.168.1.100",
            "port": 8080
        }

        envelope = create_user(params)
        event = envelope["event_plaintext"]

        # Should use empty string for missing identity_id
        assert event["peer_id"] == ""
        assert event["network_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_with_identity_id(self, initialized_db):
        """Test user creation with identity_id parameter."""
        params = {
            "identity_id": "test-identity-id",
            "address": "192.168.1.100",
            "port": 8080
        }

        envelope = create_user(params)
        event = envelope["event_plaintext"]

        # Should use provided identity_id
        assert event["peer_id"] == "test-identity-id"
        assert event["network_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_deterministic_id(self, initialized_db):
        """Test that user_id is empty until handlers process."""
        identity_id = "test-identity-id"
        
        params = {
            "identity_id": identity_id,
            "address": "192.168.1.100",
            "port": 8080
        }
        
        # user_id should be empty until handlers process
        envelope1 = create_user(params)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelope2 = create_user(params)

        # Both should have empty user_id initially
        assert envelope1["event_plaintext"]["user_id"] == ""
        assert envelope2["event_plaintext"]["user_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_port_validation(self, initialized_db):
        """Test port number handling."""
        identity_id = "test-identity-id"
        
        # Valid ports
        for port in [1, 80, 443, 8080, 65535]:
            params = {
                "identity_id": identity_id,
                "port": port
            }
            envelope = create_user(params)
            assert envelope["event_plaintext"]["port"] == port
        
        # Port as string should be converted
        params = {
            "identity_id": identity_id,
            "port": "8080"
        }
        envelope = create_user(params)
        assert envelope["event_plaintext"]["port"] == 8080
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_ipv6_address(self, initialized_db):
        """Test creating user with IPv6 address."""
        identity_id = "test-identity-id"
        
        params = {
            "identity_id": identity_id,
            "address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "port": 8080
        }
        
        envelope = create_user(params)
        event = envelope["event_plaintext"]
        
        assert event["address"] == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_hostname_address(self, initialized_db):
        """Test creating user with hostname as address."""
        identity_id = "test-identity-id"
        
        params = {
            "identity_id": identity_id,
            "address": "example.com",
            "port": 8080
        }
        
        envelope = create_user(params)
        event = envelope["event_plaintext"]
        
        assert event["address"] == "example.com"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_dependencies(self, initialized_db):
        """Test that user event declares correct dependencies."""
        identity_id = "test-identity-id"
        
        params = {
            "identity_id": identity_id
        }
        
        envelope = create_user(params)
        
        # Should depend on identity existing
        assert envelope["deps"] == [f"identity:test-identity-id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_user_timestamp(self, initialized_db):
        """Test that user event has valid timestamp."""
        identity_id = "test-identity-id"
        
        before = int(time.time() * 1000)
        
        params = {
            "identity_id": identity_id
        }
        
        envelope = create_user(params)
        created_at = envelope["event_plaintext"]["created_at"]
        
        after = int(time.time() * 1000)
        
        # Timestamp should be in valid range
        assert before <= created_at <= after


class TestJoinCommand:
    """Test join network command."""

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_network_basic(self, initialized_db):
        """Test basic network join structure."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            "invite_link": invite_link
        }

        envelope = join_network(params)

        # Should emit exactly one envelope (user event)
        # Single envelope returned

        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "user"
        assert envelope["self_created"] == True

        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "user"
        assert event["network_id"] == "test-network"
        assert event["group_id"] == "test-group"
        assert "invite_pubkey" in event
        assert "invite_signature" in event
        assert "peer_id" in event
        assert "name" in event
        assert "created_at" in event
        assert "signature" in event

        # Should generate unique peer_id
        assert event["peer_id"] != ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_network_with_name(self, initialized_db):
        """Test join network with custom name."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        # Join with custom name
        params = {
            "invite_link": invite_link,
            "name": "Alice"
        }

        envelope = join_network(params)
        event = envelope["event_plaintext"]

        assert event["name"] == "Alice"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_invalid_invite_link(self, initialized_db):
        """Test join network with invalid invite_link raises error."""
        params: Dict[str, Any] = {
            "invite_link": "invalid-link"
        }

        with pytest.raises(ValueError, match="Invalid invite link format"):
            join_network(params)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_with_invite_link(self, initialized_db):
        """Test join network with invite_link parameter."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            "invite_link": invite_link
        }

        envelope = join_network(params)
        event = envelope["event_plaintext"]

        # Should use provided invite_link data
        assert event["network_id"] == "test-network"
        assert event["group_id"] == "test-group"
        assert "invite_pubkey" in event
        assert "invite_signature" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_with_all_parameters(self, initialized_db):
        """Test join network with all parameters provided."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            "invite_link": invite_link,
            "name": "TestUser"
        }

        envelope = join_network(params)
        event = envelope["event_plaintext"]

        # Should use provided parameters
        assert event["network_id"] == "test-network"
        assert event["group_id"] == "test-group"
        assert event["name"] == "TestUser"
        assert "invite_pubkey" in event
        assert "invite_signature" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_default_name_generation(self, initialized_db):
        """Test that default name is generated from peer_id."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            "invite_link": invite_link
        }

        envelope = join_network(params)
        event = envelope["event_plaintext"]

        # Default name should be generated from peer_id
        peer_id = event["peer_id"]
        expected_name = f"User-{peer_id[:8]}"
        assert event["name"] == expected_name
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_generates_keypair(self, initialized_db):
        """Test that join generates a keypair and stores private key."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            "invite_link": invite_link
        }

        envelope = join_network(params)
        event = envelope["event_plaintext"]

        # Should generate peer_id and store keypair
        assert event["peer_id"] != ""
        assert "secret" in envelope
        assert "private_key" in envelope["secret"]
        assert "public_key" in envelope["secret"]

        # peer_id should match public key in hex
        assert event["peer_id"] == envelope["secret"]["public_key"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_default_name_format(self, initialized_db):
        """Test that default name has expected format."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        # Join without name
        envelope = join_network({"invite_link": invite_link})
        event = envelope["event_plaintext"]

        # Check default name format
        assert event["name"].startswith("User-")
        assert len(event["name"]) == 13  # "User-" + 8 chars
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_envelope_structure(self, initialized_db):
        """Test that the envelope has correct structure for pipeline processing."""
        # Create a valid invite link
        import json
        import base64
        invite_data = {
            "invite_secret": "test-secret",
            "network_id": "test-network",
            "group_id": "test-group"
        }
        invite_b64 = base64.b64encode(json.dumps(invite_data).encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        # Join
        envelope = join_network({"invite_link": invite_link})

        # Required fields for pipeline
        assert envelope["event_type"] == "user"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == envelope["event_plaintext"]["peer_id"]
        assert envelope["network_id"] == "test-network"

        # Check dependencies
        assert "deps" in envelope
        assert len(envelope["deps"]) == 1
        assert envelope["deps"][0].startswith("invite:")