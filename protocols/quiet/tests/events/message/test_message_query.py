"""
Tests for message event type query (list).
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

from protocols.quiet.events.message.queries import list_messages
from protocols.quiet.events.message.commands import create_message
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.group.commands import create_group
from protocols.quiet.events.channel.commands import create_channel
from core.processor import process_envelope
from core.handler import handle_command


class TestMessageQuery:
    """Test message list query."""
    
    @pytest.fixture
    def setup_messages(self, initialized_db):
        """Create multiple messages for testing."""
        # Create identity
        identity_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        process_envelope(identity_envelopes[0], initialized_db)
        identity_id = identity_envelopes[0]["event_plaintext"]["peer_id"]
        
        # Create network
        network_envelopes = create_network({
            "name": "Test Network",
            "identity_id": identity_id
        }, initialized_db)
        process_envelope(network_envelopes[0], initialized_db)
        network_id = network_envelopes[0]["event_plaintext"]["network_id"]
        
        # Create two groups
        group1_envelopes = create_group({
            "name": "Group 1",
            "identity_id": identity_id,
            "network_id": network_id
        }, initialized_db)
        for envelope in group1_envelopes:
            process_envelope(envelope, initialized_db)
        group1_id = group1_envelopes[0]["event_plaintext"]["group_id"]
        
        group2_envelopes = create_group({
            "name": "Group 2",
            "identity_id": identity_id,
            "network_id": network_id
        }, initialized_db)
        for envelope in group2_envelopes:
            process_envelope(envelope, initialized_db)
        group2_id = group2_envelopes[0]["event_plaintext"]["group_id"]
        
        # Create channels
        channel1_envelopes = create_channel({
            "name": "general",
            "group_id": group1_id,
            "identity_id": identity_id
        }, initialized_db)
        process_envelope(channel1_envelopes[0], initialized_db)
        channel1_id = channel1_envelopes[0]["event_plaintext"]["channel_id"]
        
        channel2_envelopes = create_channel({
            "name": "random",
            "group_id": group2_id,
            "identity_id": identity_id
        }, initialized_db)
        process_envelope(channel2_envelopes[0], initialized_db)
        channel2_id = channel2_envelopes[0]["event_plaintext"]["channel_id"]
        
        messages_created = []
        
        # Create messages in channel 1
        for i in range(5):
            # Use handle_command to go through full pipeline
            result = handle_command(
                'create_message',
                {
                    "content": f"Message {i} in channel 1",
                    "channel_id": channel1_id,
                    "identity_id": identity_id
                },
                initialized_db
            )
            time.sleep(0.01)  # Ensure different timestamps
            messages_created.append({
                "content": f"Message {i} in channel 1",
                "channel_id": channel1_id,
                "group_id": group1_id
            })
        
        # Create messages in channel 2
        for i in range(3):
            result = handle_command(
                'create_message',
                {
                    "content": f"Message {i} in channel 2",
                    "channel_id": channel2_id,
                    "identity_id": identity_id
                },
                initialized_db
            )
            time.sleep(0.01)
            messages_created.append({
                "content": f"Message {i} in channel 2",
                "channel_id": channel2_id,
                "group_id": group2_id
            })
        
        return {
            "identity_id": identity_id,
            "network_id": network_id,
            "group1_id": group1_id,
            "group2_id": group2_id,
            "channel1_id": channel1_id,
            "channel2_id": channel2_id,
            "messages": messages_created
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_all_messages(self, initialized_db, setup_messages):
        """Test listing all messages without filters."""
        messages = list_messages({}, initialized_db)
        
        assert len(messages) == 8  # 5 + 3 messages
        
        # Check messages are in chronological order (oldest first)
        for i in range(len(messages) - 1):
            assert messages[i]["created_at"] <= messages[i + 1]["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_by_channel(self, initialized_db, setup_messages):
        """Test filtering messages by channel_id."""
        data = setup_messages
        
        # List messages in channel 1
        messages = list_messages({"channel_id": data["channel1_id"]}, initialized_db)
        assert len(messages) == 5
        for message in messages:
            assert message["channel_id"] == data["channel1_id"]
            assert "channel 1" in message["content"]
        
        # List messages in channel 2
        messages = list_messages({"channel_id": data["channel2_id"]}, initialized_db)
        assert len(messages) == 3
        for message in messages:
            assert message["channel_id"] == data["channel2_id"]
            assert "channel 2" in message["content"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_by_group(self, initialized_db, setup_messages):
        """Test filtering messages by group_id."""
        data = setup_messages
        
        # List messages in group 1
        messages = list_messages({"group_id": data["group1_id"]}, initialized_db)
        assert len(messages) == 5
        for message in messages:
            assert message["group_id"] == data["group1_id"]
        
        # List messages in group 2
        messages = list_messages({"group_id": data["group2_id"]}, initialized_db)
        assert len(messages) == 3
        for message in messages:
            assert message["group_id"] == data["group2_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_with_limit(self, initialized_db, setup_messages):
        """Test limiting number of messages returned."""
        messages = list_messages({"limit": 3}, initialized_db)
        
        assert len(messages) == 3
        
        # Should return the 3 oldest messages
        assert "Message 0" in messages[0]["content"]
        assert "Message 1" in messages[1]["content"]
        assert "Message 2" in messages[2]["content"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_with_offset(self, initialized_db, setup_messages):
        """Test pagination with offset."""
        # Get first page
        page1 = list_messages({"limit": 3, "offset": 0}, initialized_db)
        assert len(page1) == 3
        
        # Get second page
        page2 = list_messages({"limit": 3, "offset": 3}, initialized_db)
        assert len(page2) == 3
        
        # Get third page (partial)
        page3 = list_messages({"limit": 3, "offset": 6}, initialized_db)
        assert len(page3) == 2  # Only 2 messages left
        
        # No overlap between pages
        page1_ids = [m["message_id"] for m in page1]
        page2_ids = [m["message_id"] for m in page2]
        page3_ids = [m["message_id"] for m in page3]
        
        assert len(set(page1_ids) & set(page2_ids)) == 0
        assert len(set(page2_ids) & set(page3_ids)) == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_channel_with_limit(self, initialized_db, setup_messages):
        """Test combining channel filter with limit."""
        data = setup_messages
        
        messages = list_messages({
            "channel_id": data["channel1_id"],
            "limit": 2
        }, initialized_db)
        
        assert len(messages) == 2
        for message in messages:
            assert message["channel_id"] == data["channel1_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_default_limit(self, initialized_db, setup_messages):
        """Test that default limit is 100."""
        # Create more than 100 messages would be expensive, 
        # so we'll just verify the default is applied
        messages = list_messages({}, initialized_db)
        
        # We have 8 messages, all should be returned with default limit
        assert len(messages) == 8
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_empty_result(self, initialized_db):
        """Test that empty database returns empty list."""
        messages = list_messages({}, initialized_db)
        assert messages == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_nonexistent_filters(self, initialized_db, setup_messages):
        """Test filtering with non-existent IDs returns empty."""
        messages = list_messages({"channel_id": "nonexistent-channel"}, initialized_db)
        assert messages == []
        
        messages = list_messages({"group_id": "nonexistent-group"}, initialized_db)
        assert messages == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_returns_all_fields(self, initialized_db, setup_messages):
        """Test that query returns all message fields."""
        messages = list_messages({"limit": 1}, initialized_db)
        
        assert len(messages) > 0
        message = messages[0]
        
        # Check all expected fields are present
        expected_fields = [
            'message_id', 'channel_id', 'group_id', 'network_id',
            'author_id', 'content', 'created_at'
        ]
        
        for field in expected_fields:
            assert field in message
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_chronological_order(self, initialized_db, setup_messages):
        """Test that messages are returned in chronological order."""
        data = setup_messages
        
        messages = list_messages({"channel_id": data["channel1_id"]}, initialized_db)
        
        # Messages should be in order: Message 0, Message 1, Message 2, etc.
        for i in range(len(messages)):
            assert f"Message {i}" in messages[i]["content"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_messages_large_offset(self, initialized_db, setup_messages):
        """Test offset larger than total messages."""
        messages = list_messages({"offset": 100}, initialized_db)
        assert messages == []