"""
Tests for channel event type validator.
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

from protocols.quiet.events.channel.validator import validate


class TestChannelValidator:
    """Test channel event validation."""
    
    @pytest.fixture
    def valid_channel_event(self):
        """Create a valid channel event."""
        peer_id = "a" * 64  # Mock peer ID
        return {
            "event_data": {
                "type": "channel",
                "channel_id": "test-channel-id",
                "group_id": "test-group-id", 
                "name": "general",
                "network_id": "test-network",
                "creator_id": peer_id,
                "created_at": int(time.time() * 1000),
                "description": "General discussion"
            },
            "metadata": {
                "peer_id": peer_id
            }
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_channel_event(self, valid_channel_event):
        """Test validation of a valid channel event."""
        event_data = valid_channel_event["event_data"]
        metadata = valid_channel_event["metadata"]
        
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_missing_required_fields(self, valid_channel_event):
        """Test that missing required fields fail validation."""
        metadata = valid_channel_event["metadata"]
        required_fields = ['type', 'channel_id', 'group_id', 'name', 'network_id', 'creator_id', 'created_at']
        
        for field in required_fields:
            event_data = valid_channel_event["event_data"].copy()
            del event_data[field]
            assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_wrong_type(self, valid_channel_event):
        """Test that wrong event type fails validation."""
        event_data = valid_channel_event["event_data"].copy()
        metadata = valid_channel_event["metadata"]
        
        event_data["type"] = "not_channel"
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_creator_mismatch(self, valid_channel_event):
        """Test that creator_id must match peer_id."""
        event_data = valid_channel_event["event_data"].copy()
        metadata = valid_channel_event["metadata"].copy()
        
        # Change creator_id to not match peer_id
        event_data["creator_id"] = "b" * 64
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_optional_description(self, valid_channel_event):
        """Test that description is optional."""
        event_data = valid_channel_event["event_data"].copy()
        metadata = valid_channel_event["metadata"]
        
        # Remove description - should still be valid
        del event_data["description"]
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_empty_name(self, valid_channel_event):
        """Test that empty channel name is technically valid."""
        event_data = valid_channel_event["event_data"].copy()
        metadata = valid_channel_event["metadata"]
        
        event_data["name"] = ""
        # Empty name passes basic validation (business rules would catch this)
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_missing_metadata(self, valid_channel_event):
        """Test validation with missing metadata."""
        event_data = valid_channel_event["event_data"]
        
        # No metadata means no peer_id to check against
        assert validate(event_data, {}) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_channel_extra_fields(self, valid_channel_event):
        """Test that extra fields don't break validation."""
        event_data = valid_channel_event["event_data"].copy()
        metadata = valid_channel_event["metadata"]
        
        # Add extra fields
        event_data["extra_field"] = "some value"
        event_data["another_field"] = 123
        
        assert validate(event_data, metadata) == True