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

from protocols.quiet.events.channel.queries import list_channels
from protocols.quiet.events.channel.commands import create_channel
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.group.commands import create_group
from core.processor import process_envelope


class TestChannelQuery:
    """Test channel list query."""
    
    @pytest.fixture
    def setup_channels(self, initialized_db):
        """Create multiple channels for testing."""
        # Create identity
        identity_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        process_envelope(identity_envelopes[0], initialized_db)
        identity_id = identity_envelopes[0]["event_plaintext"]["peer_id"]
        
        # Create two networks
        network1_envelopes = create_network({
            "name": "Network 1",
            "identity_id": identity_id
        }, initialized_db)
        process_envelope(network1_envelopes[0], initialized_db)
        network1_id = network1_envelopes[0]["event_plaintext"]["network_id"]
        
        network2_envelopes = create_network({
            "name": "Network 2", 
            "identity_id": identity_id
        }, initialized_db)
        process_envelope(network2_envelopes[0], initialized_db)
        network2_id = network2_envelopes[0]["event_plaintext"]["network_id"]
        
        # Create groups in each network
        group1_envelopes = create_group({
            "name": "Group 1",
            "identity_id": identity_id,
            "network_id": network1_id
        }, initialized_db)
        for envelope in group1_envelopes:
            process_envelope(envelope, initialized_db)
        group1_id = group1_envelopes[0]["event_plaintext"]["group_id"]
        
        group2_envelopes = create_group({
            "name": "Group 2",
            "identity_id": identity_id,
            "network_id": network2_id
        }, initialized_db)
        for envelope in group2_envelopes:
            process_envelope(envelope, initialized_db)
        group2_id = group2_envelopes[0]["event_plaintext"]["group_id"]
        
        # Create channels
        channels_created = []
        
        # Two channels in group 1
        for name in ["general", "random"]:
            envelope = create_channel({
                "name": name,
                "group_id": group1_id,
                "identity_id": identity_id,
                "description": f"{name} channel"
            }, initialized_db)[0]
            process_envelope(envelope, initialized_db)
            channels_created.append(envelope["event_plaintext"])
        
        # One channel in group 2
        envelope = create_channel({
            "name": "announcements",
            "group_id": group2_id,
            "identity_id": identity_id
        }, initialized_db)[0]
        process_envelope(envelope, initialized_db)
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
        channels = list_channels({}, initialized_db)
        
        assert len(channels) == 3
        
        # Check channels are sorted by created_at DESC
        for i in range(len(channels) - 1):
            assert channels[i]["created_at"] >= channels[i + 1]["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_channels_by_group(self, initialized_db, setup_channels):
        """Test filtering channels by group_id."""
        data = setup_channels
        
        # List channels in group 1
        channels = list_channels({"group_id": data["group1_id"]}, initialized_db)
        assert len(channels) == 2
        for channel in channels:
            assert channel["group_id"] == data["group1_id"]
            assert channel["name"] in ["general", "random"]
        
        # List channels in group 2
        channels = list_channels({"group_id": data["group2_id"]}, initialized_db)
        assert len(channels) == 1
        assert channels[0]["group_id"] == data["group2_id"]
        assert channels[0]["name"] == "announcements"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_channels_by_network(self, initialized_db, setup_channels):
        """Test filtering channels by network_id."""
        data = setup_channels
        
        # List channels in network 1
        channels = list_channels({"network_id": data["network1_id"]}, initialized_db)
        assert len(channels) == 2
        for channel in channels:
            assert channel["network_id"] == data["network1_id"]
        
        # List channels in network 2
        channels = list_channels({"network_id": data["network2_id"]}, initialized_db)
        assert len(channels) == 1
        assert channels[0]["network_id"] == data["network2_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_channels_by_group_and_network(self, initialized_db, setup_channels):
        """Test filtering channels by both group_id and network_id."""
        data = setup_channels
        
        # Should return channels matching both filters
        channels = list_channels({
            "group_id": data["group1_id"],
            "network_id": data["network1_id"]
        }, initialized_db)
        
        assert len(channels) == 2
        for channel in channels:
            assert channel["group_id"] == data["group1_id"]
            assert channel["network_id"] == data["network1_id"]
        
        # Mismatched filters should return empty
        channels = list_channels({
            "group_id": data["group1_id"],
            "network_id": data["network2_id"]  # Group 1 is in network 1, not 2
        }, initialized_db)
        assert len(channels) == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_channels_empty_result(self, initialized_db):
        """Test that empty database returns empty list."""
        channels = list_channels({}, initialized_db)
        assert channels == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_channels_nonexistent_filters(self, initialized_db, setup_channels):
        """Test filtering with non-existent IDs returns empty."""
        channels = list_channels({"group_id": "nonexistent-group"}, initialized_db)
        assert channels == []
        
        channels = list_channels({"network_id": "nonexistent-network"}, initialized_db)
        assert channels == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_channels_returns_all_fields(self, initialized_db, setup_channels):
        """Test that query returns all channel fields."""
        channels = list_channels({}, initialized_db)
        
        assert len(channels) > 0
        channel = channels[0]
        
        # Check all expected fields are present
        expected_fields = [
            'channel_id', 'group_id', 'network_id', 
            'name', 'creator_id', 'created_at', 'description'
        ]
        
        for field in expected_fields:
            assert field in channel