"""
Tests for group event type query (list).
"""
import pytest
import sys
import json
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.group.queries import get as get_groups
from protocols.quiet.events.group.commands import create_group
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.add.commands import create_add
# from core.pipeline import PipelineRunner  # Use if needed


class TestGroupQuery:
    """Test group list query."""
    
    @pytest.fixture
    def setup_groups(self, initialized_db):
        """Create multiple groups for testing."""
        # Create two identities
        identity1_envelope = create_identity({"network_id": "test-network"})
        # Process through pipeline if needed
        identity1_id = identity1_envelope["event_plaintext"]["peer_id"]
        
        identity2_envelope = create_identity({"network_id": "test-network"})
        # Process through pipeline if needed
        identity2_id = identity2_envelope["event_plaintext"]["peer_id"]
        
        # Create two networks
        network1_envelope, identity1_envelope = create_network({
            "name": "Network 1",
            "identity_id": identity1_id
        })
        # Process through pipeline if needed
        network1_id = network1_envelope["event_plaintext"]["network_id"]
        
        network2_envelope, identity2_envelope = create_network({
            "name": "Network 2",
            "identity_id": identity2_id
        })
        # Process through pipeline if needed
        network2_id = network2_envelope["event_plaintext"]["network_id"]
        
        groups_created = []
        
        # Create groups in network 1
        for name in ["Engineering", "Marketing"]:
            envelope = create_group({
                "name": name,
                "network_id": network1_id,
                "identity_id": identity1_id
            })
        # Process through pipeline if needed
            groups_created.append(envelope["event_plaintext"])
        
        # Create group in network 2
        envelope = create_group({
            "name": "Sales",
            "network_id": network2_id,
            "identity_id": identity2_id
        })
        # Process through pipeline if needed
        groups_created.append(envelope["event_plaintext"])
        
        # Add identity2 to Engineering group in network1
        engineering_group_id = groups_created[0]["group_id"]
        add_envelope = create_add({
            "group_id": engineering_group_id,
            "user_id": identity2_id,
            "identity_id": identity1_id  # identity1 is adding identity2
        })
        # Process through pipeline if needed
        return {
            "identity1_id": identity1_id,
            "identity2_id": identity2_id,
            "network1_id": network1_id,
            "network2_id": network2_id,
            "groups": groups_created,
            "engineering_group_id": engineering_group_id
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_all_groups(self, initialized_db, setup_groups):
        """Test listing all groups without filters."""
        groups = get_groups(initialized_db, {})
        
        assert len(groups) == 3
        
        # Check groups are sorted by created_at DESC
        for i in range(len(groups) - 1):
            assert groups[i]["created_at"] >= groups[i + 1]["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_by_network(self, initialized_db, setup_groups):
        """Test filtering groups by network_id."""
        data = setup_groups
        
        # List groups in network 1
        groups = get_groups(initialized_db, {"network_id": data["network1_id"]})
        assert len(groups) == 2
        for group in groups:
            assert group["network_id"] == data["network1_id"]
            assert group["name"] in ["Engineering", "Marketing"]
        
        # List groups in network 2
        groups = get_groups(initialized_db, {"network_id": data["network2_id"]})
        assert len(groups) == 1
        assert groups[0]["network_id"] == data["network2_id"]
        assert groups[0]["name"] == "Sales"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_by_user(self, initialized_db, setup_groups):
        """Test filtering groups by user membership."""
        data = setup_groups
        
        # List groups for identity1 (member of Engineering and Marketing)
        groups = get_groups(initialized_db, {"user_id": data["identity1_id"]})
        assert len(groups) == 2
        group_names = [g["name"] for g in groups]
        assert set(group_names) == {"Engineering", "Marketing"}
        
        # List groups for identity2 (member of Engineering and Sales)
        groups = get_groups(initialized_db, {"user_id": data["identity2_id"]})
        assert len(groups) == 2
        group_names = [g["name"] for g in groups]
        assert set(group_names) == {"Engineering", "Sales"}
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_by_user_and_network(self, initialized_db, setup_groups):
        """Test filtering groups by both user_id and network_id."""
        data = setup_groups
        
        # Identity1's groups in network1
        groups = get_groups(initialized_db, {
            "user_id": data["identity1_id"],
            "network_id": data["network1_id"]
        })
        assert len(groups) == 2
        for group in groups:
            assert group["network_id"] == data["network1_id"]
        
        # Identity2's groups in network1 (only Engineering)
        groups = get_groups(initialized_db, {
            "user_id": data["identity2_id"],
            "network_id": data["network1_id"]
        })
        assert len(groups) == 1
        assert groups[0]["name"] == "Engineering"
        
        # Identity2's groups in network2 (only Sales)
        groups = get_groups(initialized_db, {
            "user_id": data["identity2_id"],
            "network_id": data["network2_id"]
        })
        assert len(groups) == 1
        assert groups[0]["name"] == "Sales"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_permissions_parsed(self, initialized_db, setup_groups):
        """Test that permissions JSON is parsed."""
        groups = get_groups(initialized_db, {})
        
        assert len(groups) > 0
        for group in groups:
            # Permissions should be a dict, not a string
            assert isinstance(group["permissions"], dict)
            
            # Check expected permission structure
            if group["permissions"]:  # Some groups might have empty permissions
                for perm_name, perm_value in group["permissions"].items():
                    assert isinstance(perm_value, list)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_empty_result(self, initialized_db):
        """Test that empty database returns empty list."""
        groups = get_groups(initialized_db, {})
        assert groups == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_nonexistent_filters(self, initialized_db, setup_groups):
        """Test filtering with non-existent IDs returns empty."""
        groups = get_groups(initialized_db, {"network_id": "nonexistent-network"})
        assert groups == []
        
        groups = get_groups(initialized_db, {"user_id": "nonexistent-user"})
        assert groups == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_returns_all_fields(self, initialized_db, setup_groups):
        """Test that query returns all group fields."""
        groups = get_groups(initialized_db, {})
        
        assert len(groups) > 0
        group = groups[0]
        
        # Check all expected fields are present
        expected_fields = [
            'group_id', 'network_id', 'name', 
            'creator_id', 'owner_id', 'created_at', 'permissions'
        ]
        
        for field in expected_fields:
            assert field in group
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_groups_user_not_in_any(self, initialized_db, setup_groups):
        """Test that user with no group memberships returns empty."""
        # Create a new identity with no group memberships
        new_identity_envelope = create_identity({"network_id": "test-network"})
        # Process through pipeline if needed
        new_identity_id = new_identity_envelope["event_plaintext"]["peer_id"]
        
        groups = get_groups(initialized_db, {"user_id": new_identity_id})
        assert groups == []