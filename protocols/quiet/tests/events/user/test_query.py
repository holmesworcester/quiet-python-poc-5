"""
Tests for user event type query (list).
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.user.queries import get as get_users, get_user, get_user_by_peer_id, count_users, is_user_in_network
from protocols.quiet.events.user.commands import create_user
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.network.commands import create_network
from core.pipeline import PipelineRunner


class TestUserQuery:
    """Test user queries."""
    
    @pytest.fixture
    def setup_users(self, initialized_db):
        """Create multiple users for testing."""
        # Create two networks
        identity1_envelope = create_identity({"network_id": "network1"})
        # Process through pipeline if needed
        identity1_id = identity1_envelope["event_plaintext"]["peer_id"]
        
        identity2_envelope = create_identity({"network_id": "network2"})
        # Process through pipeline if needed
        identity2_id = identity2_envelope["event_plaintext"]["peer_id"]
        
        # Create network records
        network1_envelope, identity1_envelope = create_network({
            "name": "Network 1",
            "identity_id": identity1_id
        })
        # Process through pipeline if needed
        network2_envelope, identity2_envelope = create_network({
            "name": "Network 2", 
            "identity_id": identity2_id
        })
        # Process through pipeline if needed
        # Create users
        users_created = []
        
        # Create user in network1
        user1_envelope = create_user({
            "identity_id": identity1_id,
            "address": "192.168.1.100",
            "port": 8080
        })
        # Process through pipeline if needed
        users_created.append(user1_envelope["event_plaintext"])
        
        # Create another identity in network1 and its user
        identity3_envelope = create_identity({"network_id": "network1"})
        # Process through pipeline if needed
        identity3_id = identity3_envelope["event_plaintext"]["peer_id"]
        
        user2_envelope = create_user({
            "identity_id": identity3_id,
            "address": "192.168.1.101",
            "port": 8081
        })
        # Process through pipeline if needed
        users_created.append(user2_envelope["event_plaintext"])
        
        # Create user in network2
        user3_envelope = create_user({
            "identity_id": identity2_id,
            "address": "10.0.0.1",
            "port": 9000
        })
        # Process through pipeline if needed
        users_created.append(user3_envelope["event_plaintext"])
        
        return {
            "network1_id": "network1",
            "network2_id": "network2",
            "identity1_id": identity1_id,
            "identity2_id": identity2_id,
            "identity3_id": identity3_id,
            "users": users_created
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_users(self, initialized_db, setup_users):
        """Test listing users in a network."""
        data = setup_users
        
        # List users in network1
        users = get_users(initialized_db, {"network_id": data["network1_id"]})
        assert len(users) == 2
        
        # Check users are sorted by joined_at DESC
        for i in range(len(users) - 1):
            assert users[i]["joined_at"] >= users[i + 1]["joined_at"]
        
        # List users in network2
        users = get_users(initialized_db, {"network_id": data["network2_id"]})
        assert len(users) == 1
        assert users[0]["peer_id"] == data["identity2_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_users_with_limit(self, initialized_db, setup_users):
        """Test limiting number of users returned."""
        data = setup_users
        
        users = get_users(initialized_db, {
            "network_id": data["network1_id"],
            "limit": 1
        })
        
        assert len(users) == 1
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_users_with_offset(self, initialized_db, setup_users):
        """Test pagination with offset."""
        data = setup_users
        
        # Get first user
        page1 = get_users(initialized_db, {
            "network_id": data["network1_id"],
            "limit": 1,
            "offset": 0
        })
        assert len(page1) == 1
        
        # Get second user
        page2 = get_users(initialized_db, {
            "network_id": data["network1_id"],
            "limit": 1,
            "offset": 1
        })
        assert len(page2) == 1
        
        # Different users
        assert page1[0]["user_id"] != page2[0]["user_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_users_includes_name(self, initialized_db, setup_users):
        """Test that user list includes identity names."""
        data = setup_users
        
        users = get_users(initialized_db, {"network_id": data["network1_id"]})
        
        # Names should be included from identity join
        for user in users:
            assert "name" in user
            assert user["name"] is not None
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_user(self, initialized_db, setup_users):
        """Test getting a specific user by ID."""
        data = setup_users
        user_id = data["users"][0]["user_id"]
        
        user = get_user(initialized_db, {"user_id": user_id})
        
        assert user is not None
        assert user["user_id"] == user_id
        assert user["peer_id"] == data["identity1_id"]
        assert user["network_id"] == data["network1_id"]
        assert "name" in user
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_user_not_found(self, initialized_db, setup_users):
        """Test getting non-existent user returns None."""
        user = get_user(initialized_db, {"user_id": "non-existent"})
        assert user is None
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_user_by_peer_id(self, initialized_db, setup_users):
        """Test getting user by peer ID."""
        data = setup_users
        
        user = get_user_by_peer_id(initialized_db, {
            "peer_id": data["identity1_id"],
            "network_id": data["network1_id"]
        })
        
        assert user is not None
        assert user["peer_id"] == data["identity1_id"]
        assert user["network_id"] == data["network1_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_user_by_peer_id_not_in_network(self, initialized_db, setup_users):
        """Test getting user by peer ID in wrong network."""
        data = setup_users
        
        # identity1 is in network1, not network2
        user = get_user_by_peer_id(initialized_db, {
            "peer_id": data["identity1_id"],
            "network_id": data["network2_id"]
        })
        
        assert user is None
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_count_users(self, initialized_db, setup_users):
        """Test counting users in networks."""
        data = setup_users
        
        # Count in network1
        count = count_users(initialized_db, {"network_id": data["network1_id"]})
        assert count == 2
        
        # Count in network2
        count = count_users(initialized_db, {"network_id": data["network2_id"]})
        assert count == 1
        
        # Count in non-existent network
        count = count_users(initialized_db, {"network_id": "non-existent"})
        assert count == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_is_user_in_network(self, initialized_db, setup_users):
        """Test checking if peer is user in network."""
        data = setup_users
        
        # identity1 is in network1
        assert is_user_in_network(initialized_db, {
            "peer_id": data["identity1_id"],
            "network_id": data["network1_id"]
        }) == True
        
        # identity1 is not in network2
        assert is_user_in_network(initialized_db, {
            "peer_id": data["identity1_id"],
            "network_id": data["network2_id"]
        }) == False
        
        # Non-existent peer
        assert is_user_in_network(initialized_db, {
            "peer_id": "non-existent",
            "network_id": data["network1_id"]
        }) == False
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_get_users_empty_network(self, initialized_db):
        """Test listing users in network with no users."""
        users = get_users(initialized_db, {"network_id": "empty-network"})
        assert users == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_query_missing_params(self, initialized_db):
        """Test that queries validate required parameters."""
        # get_users missing network_id
        with pytest.raises(ValueError, match="network_id is required"):
            get_users(initialized_db, {})
        
        # get_user missing user_id
        with pytest.raises(ValueError, match="user_id is required"):
            get_user(initialized_db, {})
        
        # get_user_by_peer_id missing params
        with pytest.raises(ValueError, match="peer_id and network_id are required"):
            get_user_by_peer_id(initialized_db, {"peer_id": "test"})
        
        # count_users missing network_id
        with pytest.raises(ValueError, match="network_id is required"):
            count_users(initialized_db, {})
        
        # is_user_in_network missing params
        with pytest.raises(ValueError, match="peer_id and network_id are required"):
            is_user_in_network(initialized_db, {"network_id": "test"})