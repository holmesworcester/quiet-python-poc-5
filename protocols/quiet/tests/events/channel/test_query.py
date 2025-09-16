"""
Tests for channel event type query (list).
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.channel.queries import get as get_channels
from protocols.quiet.events.channel.commands import create_channel
from core.identity import create_identity
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.group.commands import create_group
# from core.pipeline import PipelineRunner  # Use if needed


class TestChannelQuery:
    """Test channel list query."""
    
    @pytest.fixture
    def setup_channels(self, initialized_db):
        """Create multiple channels for testing."""
        # Create identity
        identity_envelope = create_identity({"network_id": "test-network"})
        # Process through pipeline if needed
        identity_id = identity_envelope["event_plaintext"]["peer_id"]
        
        # Create two networks
        network1_envelope, identity1_envelope = create_network({
            "name": "Network 1",
            "identity_id": identity_id
        })
        # Process through pipeline if needed
        network1_id = network1_envelope["event_plaintext"]["network_id"]
        
        network2_envelope, identity2_envelope = create_network({
            "name": "Network 2", 
            "identity_id": identity_id
        })
        # Process through pipeline if needed
        network2_id = network2_envelope["event_plaintext"]["network_id"]
        
        # Create groups in each network
        group1_envelope = create_group({
            "name": "Group 1",
            "identity_id": identity_id,
            "network_id": network1_id
        })
        # Process through pipeline if needed
        group1_id = group1_envelope["event_plaintext"]["group_id"]
        
        group2_envelope = create_group({
            "name": "Group 2",
            "identity_id": identity_id,
            "network_id": network2_id
        })
        # Process through pipeline if needed
        group2_id = group2_envelope["event_plaintext"]["group_id"]
        
        # Create channels
        channels_created = []
        
        # Two channels in group 1
        for name in ["general", "random"]:
            envelope = create_channel({
                "name": name,
                "group_id": group1_id,
                "identity_id": identity_id,
                "description": f"{name} channel"
            })
        # Process through pipeline if needed
            channels_created.append(envelope["event_plaintext"])
        
        # One channel in group 2
        envelope = create_channel({
            "name": "announcements",
            "group_id": group2_id,
            "identity_id": identity_id
        })
        # Process through pipeline if needed
        channels_created.append(envelope["event_plaintext"])
        
        return {
            "identity_id": identity_id,
            "network1_id": network1_id,
            "network2_id": network2_id,
            "group1_id": group1_id,
            "group2_id": group2_id,
            "channels": channels_created
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_all_channels(self, initialized_db, setup_channels):
        """Test listing all channels without filters."""
        channels = get_channels(initialized_db, {})
        
        assert len(channels) == 3
        
        # Check channels are sorted by created_at DESC
        for i in range(len(channels) - 1):
            assert channels[i]["created_at"] >= channels[i + 1]["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_channels_by_group(self, initialized_db, setup_channels):
        """Test filtering channels by group_id."""
        data = setup_channels
        
        # List channels in group 1
        channels = get_channels(initialized_db, {"group_id": data["group1_id"]})
        assert len(channels) == 2
        for channel in channels:
            assert channel["group_id"] == data["group1_id"]
            assert channel["name"] in ["general", "random"]
        
        # List channels in group 2
        channels = get_channels(initialized_db, {"group_id": data["group2_id"]})
        assert len(channels) == 1
        assert channels[0]["group_id"] == data["group2_id"]
        assert channels[0]["name"] == "announcements"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_channels_by_network(self, initialized_db, setup_channels):
        """Test filtering channels by network_id."""
        data = setup_channels
        
        # List channels in network 1
        channels = get_channels(initialized_db, {"network_id": data["network1_id"]})
        assert len(channels) == 2
        for channel in channels:
            assert channel["network_id"] == data["network1_id"]
        
        # List channels in network 2
        channels = get_channels(initialized_db, {"network_id": data["network2_id"]})
        assert len(channels) == 1
        assert channels[0]["network_id"] == data["network2_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_channels_by_group_and_network(self, initialized_db, setup_channels):
        """Test filtering channels by both group_id and network_id."""
        data = setup_channels
        
        # Should return channels matching both filters
        channels = get_channels(initialized_db, {
            "group_id": data["group1_id"],
            "network_id": data["network1_id"]
        })
        
        assert len(channels) == 2
        for channel in channels:
            assert channel["group_id"] == data["group1_id"]
            assert channel["network_id"] == data["network1_id"]
        
        # Mismatched filters should return empty
        channels = get_channels(initialized_db, {
            "group_id": data["group1_id"],
            "network_id": data["network2_id"]  # Group 1 is in network 1, not 2
        })
        assert len(channels) == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_channels_empty_result(self, initialized_db):
        """Test that empty database returns empty list."""
        channels = get_channels(initialized_db, {})
        assert channels == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_channels_nonexistent_filters(self, initialized_db, setup_channels):
        """Test filtering with non-existent IDs returns empty."""
        channels = get_channels(initialized_db, {"group_id": "nonexistent-group"})
        assert channels == []
        
        channels = get_channels(initialized_db, {"network_id": "nonexistent-network"})
        assert channels == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_channels_returns_all_fields(self, initialized_db, setup_channels):
        """Test that query returns all channel fields."""
        channels = get_channels(initialized_db, {})
        
        assert len(channels) > 0
        channel = channels[0]
        
        # Check all expected fields are present
        expected_fields = [
            'channel_id', 'group_id', 'network_id', 
            'name', 'creator_id', 'created_at', 'description'
        ]
        
        for field in expected_fields:
            assert field in channel