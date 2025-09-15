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
from protocols.quiet.tests.conftest import process_envelope


class TestChannelCommand:
    """Test channel creation command."""
    
    @pytest.fixture
    def setup_network_and_identity(self, initialized_db):
        """Create identity, network, and group for channel tests."""
        # Create identity
        identity_envelope = create_identity({"network_id": "test-network"})
        identity_id = identity_envelope["event_plaintext"]["peer_id"]

        # Use mock IDs since commands don't generate them
        network_id = "test-network-id"
        group_id = "test-group-id"

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
            "network_id": network_id,
        }

        envelope = create_channel(params)
        
        # Should emit exactly one envelope
        # Single envelope returned

        assert envelope["event_type"] == "channel"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_id
        assert envelope["network_id"] == network_id
        assert envelope["deps"] == [f"group:{group_id}"]
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "channel"
        assert event["name"] == "general"
        assert event["group_id"] == group_id
        assert event["network_id"] == network_id
        assert event["creator_id"] == identity_id
        assert event["channel_id"] == ""  # Empty until handlers process
        assert "created_at" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_missing_params(self):
        """Test that commands work with missing params (no validation)."""
        # Commands don't validate - they just use defaults
        envelope = create_channel({"group_id": "test-group", "identity_id": "test-id"})
        assert envelope["event_plaintext"]["name"] == ""  # Empty default

        envelope = create_channel({"name": "general", "identity_id": "test-id"})
        assert envelope["event_plaintext"]["group_id"] == ""  # Empty default

        envelope = create_channel({"name": "general", "group_id": "test-group"})
        assert envelope["event_plaintext"]["creator_id"] == ""  # Empty default
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_channels(self, initialized_db, setup_network_and_identity):
        """Test creating multiple channels in same group."""
        identity_id, network_id, group_id = setup_network_and_identity
        
        # Create first channel
        params1 = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id,
            "network_id": network_id
        }
        envelope1 = create_channel(params1)

        # Create second channel
        params2 = {
            "name": "random",
            "group_id": group_id,
            "identity_id": identity_id,
            "network_id": network_id
        }
        envelope2 = create_channel(params2)

        # Both have empty IDs until handlers process
        assert envelope1["event_plaintext"]["channel_id"] == ""
        assert envelope2["event_plaintext"]["channel_id"] == ""
        # But different names
        assert envelope1["event_plaintext"]["name"] != envelope2["event_plaintext"]["name"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_deterministic_id(self, initialized_db, setup_network_and_identity):
        """Test that channels have different timestamps."""
        identity_id, network_id, group_id = setup_network_and_identity

        # Create channel with specific timestamp
        params = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id,
            "network_id": network_id
        }

        # Two channels created at different times should have different timestamps
        envelope1 = create_channel(params)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelope2 = create_channel(params)

        # IDs are empty until handlers, but timestamps differ
        assert envelope1["event_plaintext"]["created_at"] != envelope2["event_plaintext"]["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_empty_description(self, initialized_db, setup_network_and_identity):
        """Test creating channel without description."""
        identity_id, network_id, group_id = setup_network_and_identity

        params = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id,
            "network_id": network_id
        }

        envelope = create_channel(params)
        event = envelope["event_plaintext"]
        
        # No description field for channels
        assert "description" not in event