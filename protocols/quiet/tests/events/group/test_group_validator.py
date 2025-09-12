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
                "permissions": {
                    "invite": ["creator", "admin"],
                    "remove": ["creator", "admin"],
                    "message": ["all"]
                }
            },
            "metadata": {
                "peer_id": peer_id
            }
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_valid_group_event(self, valid_group_event):
        """Test validation of a valid group event."""
        event_data = valid_group_event["event_data"]
        metadata = valid_group_event["metadata"]
        
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_missing_required_fields(self, valid_group_event):
        """Test that missing required fields fail validation."""
        metadata = valid_group_event["metadata"]
        required_fields = ['type', 'group_id', 'name', 'network_id', 'creator_id', 'created_at', 'permissions']
        
        for field in required_fields:
            event_data = valid_group_event["event_data"].copy()
            del event_data[field]
            assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_wrong_type(self, valid_group_event):
        """Test that wrong event type fails validation."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        event_data["type"] = "not_group"
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_creator_mismatch(self, valid_group_event):
        """Test that creator_id must match peer_id."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"].copy()
        
        # Change creator_id to not match peer_id
        event_data["creator_id"] = "b" * 64
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_invalid_permissions_type(self, valid_group_event):
        """Test that permissions must be a dict."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        # Permissions as list instead of dict
        event_data["permissions"] = ["invite", "remove"]
        assert validate(event_data, metadata) == False
        
        # Permissions as string
        event_data["permissions"] = "all"
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_invalid_permission_names(self, valid_group_event):
        """Test that only valid permission names are allowed."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        # Add invalid permission
        event_data["permissions"]["delete_everything"] = ["admin"]
        assert validate(event_data, metadata) == False
        
        # Only invalid permissions
        event_data["permissions"] = {
            "hack": ["all"],
            "destroy": ["admin"]
        }
        assert validate(event_data, metadata) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_empty_permissions(self, valid_group_event):
        """Test that empty permissions dict is valid."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        event_data["permissions"] = {}
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_subset_permissions(self, valid_group_event):
        """Test that having only some permissions is valid."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        # Only invite permission
        event_data["permissions"] = {
            "invite": ["admin"]
        }
        assert validate(event_data, metadata) == True
        
        # Only message permission
        event_data["permissions"] = {
            "message": ["all"]
        }
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_missing_metadata(self, valid_group_event):
        """Test validation with missing metadata."""
        event_data = valid_group_event["event_data"]
        
        # No metadata means no peer_id to check against
        assert validate(event_data, {}) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_extra_fields(self, valid_group_event):
        """Test that extra fields don't break validation."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        # Add extra fields
        event_data["description"] = "Engineering team group"
        event_data["member_count"] = 42
        
        assert validate(event_data, metadata) == True
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_group_permission_values_not_validated(self, valid_group_event):
        """Test that permission values are not validated (just structure)."""
        event_data = valid_group_event["event_data"].copy()
        metadata = valid_group_event["metadata"]
        
        # Invalid permission values should still pass basic validation
        event_data["permissions"] = {
            "invite": "everyone",  # Should be a list
            "remove": 123,  # Should be a list
            "message": {"role": "admin"}  # Should be a list
        }
        
        # Basic validator only checks permission names, not values
        assert validate(event_data, metadata) == True