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
from core.api import API


class TestGroupCommand:
    """Test group creation command."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_basic(self):
        """Test basic group creation."""
        params = {
            "name": "Engineering",
            "network_id": "test-network",
            "identity_id": "test-identity"
        }
        
        envelope = create_group(params)
        
        # Check envelope structure
        assert envelope["event_type"] == "group"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == "test-identity"
        assert envelope["network_id"] == "test-network"
        assert envelope["deps"] == []  # No dependencies
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "group"
        assert event["name"] == "Engineering"
        assert event["network_id"] == "test-network"
        assert event["creator_id"] == "test-identity"
        assert "group_id" in event
        assert "created_at" in event
        assert event["signature"] == ""  # Unsigned
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_through_api(self, tmp_path):
        """Test creating group through API pipeline."""
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=tmp_path / "test.db")
        
        # First create network (which creates identity)
        network_result = api.create_network(name="Test Network")
        network_id = network_result["network_id"]
        identity_id = network_result["creator_id"]
        
        # Create group
        result = api.create_group(
            name="Engineering",
            network_id=network_id,
            identity_id=identity_id
        )
        
        # Check result
        assert "group_id" in result
        assert result["name"] == "Engineering"
        assert result["network_id"] == network_id
        assert result["creator_id"] == identity_id
        assert "signature" in result
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_default_values(self):
        """Test group creation with default/missing values."""
        params = {}
        
        envelope = create_group(params)
        event = envelope["event_plaintext"]
        
        # Should use empty defaults
        assert event["name"] == ""
        assert event["network_id"] == ""
        assert event["creator_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_id_generation(self):
        """Test that group ID is generated correctly."""
        params = {
            "name": "Engineering",
            "network_id": "test-network",
            "identity_id": "test-identity"
        }
        
        # Create two groups with same params
        envelope1 = create_group(params)
        time.sleep(0.01)  # Small delay to ensure different timestamp
        envelope2 = create_group(params)
        
        # Should have different IDs due to timestamp
        assert envelope1["event_plaintext"]["group_id"] != envelope2["event_plaintext"]["group_id"]
        
        # IDs should be valid hex
        assert len(envelope1["event_plaintext"]["group_id"]) == 64
        assert len(envelope2["event_plaintext"]["group_id"]) == 64
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_groups_through_api(self, tmp_path):
        """Test creating multiple groups in same network."""
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=tmp_path / "test.db")
        
        # Create network
        network_result = api.create_network(name="Test Network")
        network_id = network_result["network_id"]
        identity_id = network_result["creator_id"]
        
        # Create multiple groups
        group1 = api.create_group(
            name="Engineering",
            network_id=network_id,
            identity_id=identity_id
        )
        
        group2 = api.create_group(
            name="Marketing",
            network_id=network_id,
            identity_id=identity_id
        )
        
        # Should have different IDs
        assert group1["group_id"] != group2["group_id"]
        
        # Query for groups
        groups = api.get_groups(network_id=network_id)
        assert len(groups) == 2
        
        group_names = {g["name"] for g in groups}
        assert "Engineering" in group_names
        assert "Marketing" in group_names