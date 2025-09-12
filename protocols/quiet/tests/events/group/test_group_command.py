"""
Tests for group event type command (create).
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

from protocols.quiet.events.group.commands import create_group
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from core.processor import process_envelope


class TestGroupCommand:
    """Test group creation command."""
    
    @pytest.fixture
    def setup_network_and_identity(self, initialized_db):
        """Create identity and network for group tests."""
        # Create identity
        identity_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        process_envelope(identity_envelopes[0], initialized_db)
        identity_id = identity_envelopes[0]["event_plaintext"]["peer_id"]
        
        # Create network
        network_params = {
            "name": "Test Network",
            "identity_id": identity_id
        }
        network_envelopes = create_network(network_params, initialized_db)
        process_envelope(network_envelopes[0], initialized_db)
        network_id = network_envelopes[0]["event_plaintext"]["network_id"]
        
        return identity_id, network_id
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_basic(self, initialized_db, setup_network_and_identity):
        """Test basic group creation."""
        identity_id, network_id = setup_network_and_identity
        
        params = {
            "name": "Engineering",
            "network_id": network_id,
            "identity_id": identity_id
        }
        
        envelopes = create_group(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
        assert envelope["event_type"] == "group"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_id
        assert envelope["network_id"] == network_id
        assert envelope["group_id"] == envelope["event_plaintext"]["group_id"]
        assert envelope["deps"] == []  # No dependencies
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "group"
        assert event["name"] == "Engineering"
        assert event["network_id"] == network_id
        assert event["creator_id"] == identity_id
        assert "group_id" in event
        assert "created_at" in event
        
        # Check default permissions
        assert event["permissions"]["invite"] == ['creator', 'admin']
        assert event["permissions"]["remove"] == ['creator', 'admin']
        assert event["permissions"]["message"] == ['all']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_missing_params(self, initialized_db):
        """Test that missing required params raise errors."""
        # Missing name
        with pytest.raises(ValueError, match="name, network_id, and identity_id are required"):
            create_group({"network_id": "test-net", "identity_id": "test-id"}, initialized_db)
        
        # Missing network_id
        with pytest.raises(ValueError, match="name, network_id, and identity_id are required"):
            create_group({"name": "Engineering", "identity_id": "test-id"}, initialized_db)
        
        # Missing identity_id
        with pytest.raises(ValueError, match="name, network_id, and identity_id are required"):
            create_group({"name": "Engineering", "network_id": "test-net"}, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_invalid_identity(self, initialized_db):
        """Test that invalid identity raises error."""
        params = {
            "name": "Engineering",
            "network_id": "test-network",
            "identity_id": "non-existent-identity"
        }
        
        with pytest.raises(ValueError, match="Identity not found"):
            create_group(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_groups(self, initialized_db, setup_network_and_identity):
        """Test creating multiple groups in same network."""
        identity_id, network_id = setup_network_and_identity
        
        # Create first group
        params1 = {
            "name": "Engineering",
            "network_id": network_id,
            "identity_id": identity_id
        }
        envelopes1 = create_group(params1, initialized_db)
        group_id1 = envelopes1[0]["event_plaintext"]["group_id"]
        
        # Create second group
        params2 = {
            "name": "Marketing",
            "network_id": network_id,
            "identity_id": identity_id
        }
        envelopes2 = create_group(params2, initialized_db)
        group_id2 = envelopes2[0]["event_plaintext"]["group_id"]
        
        # Should have different group IDs
        assert group_id1 != group_id2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_deterministic_id(self, initialized_db, setup_network_and_identity):
        """Test that group ID is deterministic based on inputs."""
        identity_id, network_id = setup_network_and_identity
        
        params = {
            "name": "Engineering",
            "network_id": network_id,
            "identity_id": identity_id
        }
        
        # Two groups created at different times should have different IDs
        envelopes1 = create_group(params, initialized_db)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelopes2 = create_group(params, initialized_db)
        
        assert envelopes1[0]["event_plaintext"]["group_id"] != envelopes2[0]["event_plaintext"]["group_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_same_name_different_networks(self, initialized_db):
        """Test creating groups with same name in different networks."""
        # Create two identities and networks
        identity1_envelopes = create_identity({"network_id": "network1"}, initialized_db)
        process_envelope(identity1_envelopes[0], initialized_db)
        identity1_id = identity1_envelopes[0]["event_plaintext"]["peer_id"]
        
        network1_envelopes = create_network({
            "name": "Network 1",
            "identity_id": identity1_id
        }, initialized_db)
        process_envelope(network1_envelopes[0], initialized_db)
        network1_id = network1_envelopes[0]["event_plaintext"]["network_id"]
        
        identity2_envelopes = create_identity({"network_id": "network2"}, initialized_db)
        process_envelope(identity2_envelopes[0], initialized_db) 
        identity2_id = identity2_envelopes[0]["event_plaintext"]["peer_id"]
        
        network2_envelopes = create_network({
            "name": "Network 2",
            "identity_id": identity2_id
        }, initialized_db)
        process_envelope(network2_envelopes[0], initialized_db)
        network2_id = network2_envelopes[0]["event_plaintext"]["network_id"]
        
        # Create groups with same name in different networks
        group1_envelopes = create_group({
            "name": "General",
            "network_id": network1_id,
            "identity_id": identity1_id
        }, initialized_db)
        
        group2_envelopes = create_group({
            "name": "General",
            "network_id": network2_id,
            "identity_id": identity2_id
        }, initialized_db)
        
        # Should have different group IDs
        assert group1_envelopes[0]["event_plaintext"]["group_id"] != group2_envelopes[0]["event_plaintext"]["group_id"]
        
        # But same name
        assert group1_envelopes[0]["event_plaintext"]["name"] == group2_envelopes[0]["event_plaintext"]["name"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_permissions_structure(self, initialized_db, setup_network_and_identity):
        """Test that group permissions have correct structure."""
        identity_id, network_id = setup_network_and_identity
        
        params = {
            "name": "Engineering",
            "network_id": network_id,
            "identity_id": identity_id
        }
        
        envelopes = create_group(params, initialized_db)
        permissions = envelopes[0]["event_plaintext"]["permissions"]
        
        # Check all required permission types exist
        assert "invite" in permissions
        assert "remove" in permissions
        assert "message" in permissions
        
        # Check values are lists
        assert isinstance(permissions["invite"], list)
        assert isinstance(permissions["remove"], list)
        assert isinstance(permissions["message"], list)
        
        # Check default values
        assert set(permissions["invite"]) == {"creator", "admin"}
        assert set(permissions["remove"]) == {"creator", "admin"}
        assert permissions["message"] == ["all"]