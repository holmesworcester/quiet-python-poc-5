"""
Tests for channel event type command (create).
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

from protocols.quiet.events.channel.commands import create_channel
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.group.commands import create_group
from core.processor import process_envelope


class TestChannelCommand:
    """Test channel creation command."""
    
    @pytest.fixture
    def setup_network_and_identity(self, initialized_db):
        """Create identity, network, and group for channel tests."""
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
        
        # Create group
        group_params = {
            "name": "Test Group",
            "identity_id": identity_id,
            "network_id": network_id
        }
        group_envelopes = create_group(group_params, initialized_db)
        for envelope in group_envelopes:
            process_envelope(envelope, initialized_db)
        group_id = group_envelopes[0]["event_plaintext"]["group_id"]
        
        return identity_id, network_id, group_id
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_basic(self, initialized_db, setup_network_and_identity):
        """Test basic channel creation."""
        identity_id, network_id, group_id = setup_network_and_identity
        
        params = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id,
            "description": "General discussion"
        }
        
        envelopes = create_channel(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
        assert envelope["event_type"] == "channel"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_id
        assert envelope["network_id"] == network_id
        assert envelope["group_id"] == group_id
        assert envelope["deps"] == [group_id]
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "channel"
        assert event["name"] == "general"
        assert event["group_id"] == group_id
        assert event["network_id"] == network_id
        assert event["creator_id"] == identity_id
        assert event["description"] == "General discussion"
        assert "channel_id" in event
        assert "created_at" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_missing_params(self, initialized_db):
        """Test that missing required params raise errors."""
        # Missing name
        with pytest.raises(ValueError, match="name, group_id, and identity_id are required"):
            create_channel({"group_id": "test-group", "identity_id": "test-id"}, initialized_db)
        
        # Missing group_id
        with pytest.raises(ValueError, match="name, group_id, and identity_id are required"):
            create_channel({"name": "general", "identity_id": "test-id"}, initialized_db)
        
        # Missing identity_id
        with pytest.raises(ValueError, match="name, group_id, and identity_id are required"):
            create_channel({"name": "general", "group_id": "test-group"}, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_invalid_identity(self, initialized_db):
        """Test that invalid identity raises error."""
        params = {
            "name": "general",
            "group_id": "test-group",
            "identity_id": "non-existent-identity"
        }
        
        with pytest.raises(ValueError, match="Identity not found"):
            create_channel(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_not_group_member(self, initialized_db, setup_network_and_identity):
        """Test that non-group members cannot create channels."""
        identity_id, network_id, _ = setup_network_and_identity
        
        # Create a different group the user is not a member of
        group_params = {
            "name": "Other Group",
            "identity_id": identity_id,
            "network_id": network_id
        }
        group_envelopes = create_group(group_params, initialized_db)
        other_group_id = group_envelopes[0]["event_plaintext"]["group_id"]
        
        # Don't process the group events, so user won't be added as member
        
        params = {
            "name": "general",
            "group_id": other_group_id,
            "identity_id": identity_id
        }
        
        with pytest.raises(ValueError, match="User is not a member of the group"):
            create_channel(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_invalid_group(self, initialized_db, setup_network_and_identity):
        """Test that invalid group raises error."""
        identity_id, _, _ = setup_network_and_identity
        
        params = {
            "name": "general",
            "group_id": "non-existent-group",
            "identity_id": identity_id
        }
        
        with pytest.raises(ValueError, match="User is not a member of the group"):
            create_channel(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_channels(self, initialized_db, setup_network_and_identity):
        """Test creating multiple channels in same group."""
        identity_id, network_id, group_id = setup_network_and_identity
        
        # Create first channel
        params1 = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id
        }
        envelopes1 = create_channel(params1, initialized_db)
        channel_id1 = envelopes1[0]["event_plaintext"]["channel_id"]
        
        # Create second channel
        params2 = {
            "name": "random",
            "group_id": group_id,
            "identity_id": identity_id
        }
        envelopes2 = create_channel(params2, initialized_db)
        channel_id2 = envelopes2[0]["event_plaintext"]["channel_id"]
        
        # Should have different channel IDs
        assert channel_id1 != channel_id2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_deterministic_id(self, initialized_db, setup_network_and_identity):
        """Test that channel ID is deterministic based on inputs."""
        identity_id, _, group_id = setup_network_and_identity
        
        # Create channel with specific timestamp
        params = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id
        }
        
        # Two channels created at different times should have different IDs
        envelopes1 = create_channel(params, initialized_db)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelopes2 = create_channel(params, initialized_db)
        
        assert envelopes1[0]["event_plaintext"]["channel_id"] != envelopes2[0]["event_plaintext"]["channel_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_empty_description(self, initialized_db, setup_network_and_identity):
        """Test creating channel without description."""
        identity_id, _, group_id = setup_network_and_identity
        
        params = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id
        }
        
        envelopes = create_channel(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        # Description should be empty string
        assert event["description"] == ""