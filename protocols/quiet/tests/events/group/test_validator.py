"""
Tests for group event type validator.
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

from protocols.quiet.events.group.validator import validate


class TestGroupValidator:
    """Test group event validation."""
    
    @pytest.fixture
    def valid_group_event(self):
        """Create a valid group event."""
        peer_id = "a" * 64  # Mock peer ID
        return {
            "event_data": {
                "type": "group",
                "group_id": "test-group-id",
                "name": "Engineering",
                "network_id": "test-network",
                "creator_id": peer_id,
                "created_at": int(time.time() * 1000),
                "signature": "test-signature"
            },
            "metadata": {
                "peer_id": peer_id
            }
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_group_event(self, valid_group_event):
        """Test validation of a valid group event."""
        envelope = {
            "event_plaintext": valid_group_event["event_data"],
            "peer_id": valid_group_event["metadata"]["peer_id"]
        }
        
        assert validate(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_missing_required_fields(self, valid_group_event):
        """Test that missing required fields fail validation."""
        peer_id = valid_group_event["metadata"]["peer_id"]
        required_fields = ['type', 'group_id', 'name', 'network_id', 'creator_id', 'created_at']
        
        for field in required_fields:
            event_data = valid_group_event["event_data"].copy()
            del event_data[field]
            envelope = {"event_plaintext": event_data, "peer_id": peer_id}
            assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_wrong_type(self, valid_group_event):
        """Test that wrong event type fails validation."""
        event_data = valid_group_event["event_data"].copy()
        peer_id = valid_group_event["metadata"]["peer_id"]
        
        event_data["type"] = "not_group"
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_creator_mismatch(self, valid_group_event):
        """Test that creator_id must match peer_id."""
        event_data = valid_group_event["event_data"].copy()
        peer_id = valid_group_event["metadata"]["peer_id"]
        
        # Change creator_id to not match peer_id
        event_data["creator_id"] = "b" * 64
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == False
    
    
    
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_missing_peer_id(self, valid_group_event):
        """Test validation with missing peer_id."""
        event_data = valid_group_event["event_data"]
        
        # No peer_id in envelope
        envelope = {"event_plaintext": event_data}
        assert validate(envelope) == True  # Validation passes without peer_id check
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_extra_fields(self, valid_group_event):
        """Test that extra fields don't break validation."""
        event_data = valid_group_event["event_data"].copy()
        peer_id = valid_group_event["metadata"]["peer_id"]
        
        # Add extra fields
        event_data["description"] = "Engineering team group"
        event_data["member_count"] = 42
        
        envelope = {"event_plaintext": event_data, "peer_id": peer_id}
        assert validate(envelope) == True
    
