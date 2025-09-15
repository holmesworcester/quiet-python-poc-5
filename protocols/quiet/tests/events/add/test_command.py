"""
Tests for add event type command (create).
"""
import pytest
import sys
import json
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.add.commands import create_add
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.group.commands import create_group
from core.crypto import verify, generate_keypair


class TestAddCommand:
    """Test add user to group command."""
    
    @pytest.fixture
    def test_identity(self):
        """Create a test identity with keypair."""
        private_key, public_key = generate_keypair()
        return {
            'identity_id': public_key.hex(),
            'private_key': private_key,
            'public_key': public_key
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_user_to_group_basic(self, initialized_db, test_identity):
        """Test basic add user to group."""
        # Mock user to add
        user_private_key, user_public_key = generate_keypair()
        user_id = user_public_key.hex()
        
        # Mock group ID
        group_id = "test-group-id-12345"
        
        # Add user to group
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "identity_id": test_identity['identity_id'],
            "network_id": "test-network",
        }
        
        envelope = create_add(params)
        
        # Should emit exactly one envelope
        # Single envelope returned

        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "add"
        assert envelope["self_created"] == True
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "add"
        assert event["group_id"] == group_id
        assert event["user_id"] == user_id
        assert event["added_by"] == test_identity['identity_id']
        assert event["network_id"] == "test-network"
        assert "created_at" in event
        assert "signature" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_missing_group_id(self, initialized_db):
        """Test that missing group_id raises error."""
        params = {
            "user_id": "some-user",
            "identity_id": "some-identity",
            "network_id": "test-network"
        }
        
        with pytest.raises(ValueError, match="group_id is required"):
            create_add(params)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_missing_user_id(self, initialized_db):
        """Test that missing user_id raises error."""
        params = {
            "group_id": "some-group",
            "identity_id": "some-identity",
            "network_id": "test-network"
        }
        
        with pytest.raises(ValueError, match="user_id is required"):
            create_add(params)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_missing_identity_id(self, initialized_db):
        """Test that missing identity_id raises error."""
        params = {
            "group_id": "some-group",
            "user_id": "some-user",
            "network_id": "test-network"
        }
        
        with pytest.raises(ValueError, match="identity_id is required"):
            create_add(params)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_missing_network_id(self, initialized_db):
        """Test that missing network_id raises error."""
        params = {
            "group_id": "some-group",
            "user_id": "some-user",
            "identity_id": "some-identity",
        }
        
        with pytest.raises(ValueError, match="network_id is required"):
            create_add(params)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_multiple_users_to_group(self, initialized_db, test_identity):
        """Test adding multiple users produces different events."""
        # Mock users and group
        user1_private_key, user1_public_key = generate_keypair()
        user1_id = user1_public_key.hex()
        
        user2_private_key, user2_public_key = generate_keypair()
        user2_id = user2_public_key.hex()
        
        group_id = "test-group-id-12345"
        
        # Add first user
        envelope1 = create_add({
            "group_id": group_id,
            "user_id": user1_id,
            "identity_id": test_identity['identity_id'],
            "network_id": "test-network"
        })

        # Add second user
        envelope2 = create_add({
            "group_id": group_id,
            "user_id": user2_id,
            "identity_id": test_identity['identity_id'],
            "network_id": "test-network"
        })

        # Should produce different events for different users
        assert envelope1["event_plaintext"]["user_id"] == user1_id
        assert envelope2["event_plaintext"]["user_id"] == user2_id
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_add_envelope_structure(self, initialized_db, test_identity):
        """Test that the envelope has correct structure for pipeline processing."""
        # Mock user and group
        user_private_key, user_public_key = generate_keypair()
        user_id = user_public_key.hex()
        group_id = "test-group-id-12345"
        
        # Add user to group
        params = {
            "group_id": group_id,
            "user_id": user_id,
            "identity_id": test_identity['identity_id'],
            "network_id": "test-network",
        }
        
        envelope = create_add(params)

        # Required fields for pipeline
        assert envelope["event_type"] == "add"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == test_identity['identity_id']
        assert envelope["network_id"] == "test-network"