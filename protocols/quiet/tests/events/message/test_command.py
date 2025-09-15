"""
Tests for message event type command (create).
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

from protocols.quiet.events.message.commands import create_message
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.group.commands import create_group
from protocols.quiet.events.channel.commands import create_channel
from protocols.quiet.tests.conftest import process_envelope


class TestMessageCommand:
    """Test message creation command."""
    
    @pytest.fixture
    def setup_channel_and_identity(self, initialized_db):
        """Create identity, network, group and channel for message tests."""
        # Create identity
        identity_envelope = create_identity({"network_id": "test-network"})
        # Process through pipeline if needed
        identity_id = identity_envelope["event_plaintext"]["peer_id"]
        
        # Create network
        network_params = {
            "name": "Test Network",
            "identity_id": identity_id
        }
        network_envelope, identity_envelope = create_network(network_params)
        # Process through pipeline if needed
        network_id = network_envelope["event_plaintext"]["network_id"]
        
        # Create group
        group_params = {
            "name": "Test Group",
            "identity_id": identity_id,
            "network_id": network_id
        }
        group_envelope = create_group(group_params)
        # Process through pipeline if needed
        group_id = group_envelope["event_plaintext"]["group_id"]
        
        # Create channel
        channel_params = {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id
        }
        channel_envelope = create_channel(channel_params)
        # Process through pipeline if needed
        channel_id = channel_envelope["event_plaintext"]["channel_id"]
        
        return identity_id, network_id, group_id, channel_id
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_basic(self, initialized_db, setup_channel_and_identity):
        """Test basic message creation."""
        identity_id, network_id, group_id, channel_id = setup_channel_and_identity
        
        params = {
            "content": "Hello, world!",
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        
        envelope = create_message(params)
        
        assert envelope["event_type"] == "message"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_id
        assert envelope["deps"] == [
            f"identity:{identity_id}",
            f"channel:{channel_id}"
        ]
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "message"
        assert event["content"] == "Hello, world!"
        assert event["channel_id"] == channel_id
        assert event["peer_id"] == identity_id
        assert "message_id" in event
        assert "created_at" in event

        # These fields are empty until handlers process them
        assert event["message_id"] == ""
        assert event["group_id"] == ""
        assert event["network_id"] == ""
        assert event["signature"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_missing_params(self, initialized_db):
        """Test that missing params use defaults."""
        # Missing content - should use empty string default
        envelope = create_message({"channel_id": "test-channel", "identity_id": "test-id"})
        assert envelope["event_plaintext"]["content"] == ""

        # Missing channel_id - should use empty string default
        envelope = create_message({"content": "Hello", "identity_id": "test-id"})
        assert envelope["event_plaintext"]["channel_id"] == ""

        # Missing identity_id - should use empty string default
        envelope = create_message({"content": "Hello", "channel_id": "test-channel"})
        assert envelope["event_plaintext"]["peer_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_empty_content(self, initialized_db, setup_channel_and_identity):
        """Test creating message with empty content."""
        identity_id, _, _, channel_id = setup_channel_and_identity
        
        params = {
            "content": "",
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        
        # Empty content should be allowed
        envelope = create_message(params)
        assert envelope["event_plaintext"]["content"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_long_content(self, initialized_db, setup_channel_and_identity):
        """Test creating message with long content."""
        identity_id, _, _, channel_id = setup_channel_and_identity
        
        long_content = "A" * 10000  # 10KB of text
        params = {
            "content": long_content,
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        
        envelope = create_message(params)
        assert envelope["event_plaintext"]["content"] == long_content
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_messages(self, initialized_db, setup_channel_and_identity):
        """Test creating multiple messages in same channel."""
        identity_id, _, _, channel_id = setup_channel_and_identity

        # Create first message
        params1 = {
            "content": "First message",
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        envelope1 = create_message(params1)

        # Create second message
        params2 = {
            "content": "Second message",
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        envelope2 = create_message(params2)

        # Both should have empty message IDs until handlers process them
        assert envelope1["event_plaintext"]["message_id"] == ""
        assert envelope2["event_plaintext"]["message_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_timestamps_differ(self, initialized_db, setup_channel_and_identity):
        """Test that messages created at different times have different timestamps."""
        identity_id, _, _, channel_id = setup_channel_and_identity

        params = {
            "content": "Hello",
            "channel_id": channel_id,
            "identity_id": identity_id
        }

        # Two messages with same content at different times should have different timestamps
        envelope1 = create_message(params)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelope2 = create_message(params)

        # Both have empty message IDs but different timestamps
        assert envelope1["event_plaintext"]["message_id"] == ""
        assert envelope2["event_plaintext"]["message_id"] == ""
        assert envelope1["event_plaintext"]["created_at"] != envelope2["event_plaintext"]["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_special_characters(self, initialized_db, setup_channel_and_identity):
        """Test creating message with special characters."""
        identity_id, _, _, channel_id = setup_channel_and_identity
        
        special_content = "Hello 👋 with emojis 🎉 and unicode ñ é ü"
        params = {
            "content": special_content,
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        
        envelope = create_message(params)
        assert envelope["event_plaintext"]["content"] == special_content
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_dependencies(self, initialized_db, setup_channel_and_identity):
        """Test that message declares correct dependencies."""
        identity_id, _, _, channel_id = setup_channel_and_identity
        
        params = {
            "content": "Test dependencies",
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        
        envelope = create_message(params)
        
        # Should depend on identity (for signing) and channel (for context)
        assert len(envelope["deps"]) == 2
        assert f"identity:{identity_id}" in envelope["deps"]
        assert f"channel:{channel_id}" in envelope["deps"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_timestamp(self, initialized_db, setup_channel_and_identity):
        """Test that message has valid timestamp."""
        identity_id, _, _, channel_id = setup_channel_and_identity
        
        before = int(time.time() * 1000)
        
        params = {
            "content": "Test timestamp",
            "channel_id": channel_id,
            "identity_id": identity_id
        }
        
        envelope = create_message(params)
        created_at = envelope["event_plaintext"]["created_at"]
        
        after = int(time.time() * 1000)
        
        # Timestamp should be in valid range
        assert before <= created_at <= after
        
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_different_content(self, initialized_db, setup_channel_and_identity):
        """Test creating messages with different content."""
        identity_id, _, _, channel_id = setup_channel_and_identity

        # Create messages with different content
        params1 = {
            "content": "Message A",
            "channel_id": channel_id,
            "identity_id": identity_id
        }

        params2 = {
            "content": "Message B",
            "channel_id": channel_id,
            "identity_id": identity_id
        }

        envelope1 = create_message(params1)
        envelope2 = create_message(params2)

        # Both should have empty message IDs but different content
        assert envelope1["event_plaintext"]["message_id"] == ""
        assert envelope2["event_plaintext"]["message_id"] == ""
        assert envelope1["event_plaintext"]["content"] == "Message A"
        assert envelope2["event_plaintext"]["content"] == "Message B"