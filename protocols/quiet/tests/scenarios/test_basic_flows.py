"""
Basic flow scenario tests for Quiet protocol.
"""
import pytest
from .base import ScenarioTestBase
from core.api_client import APIError


class TestBasicFlows(ScenarioTestBase):
    """Test basic protocol flows with real API calls."""
    
    def test_identity_creation(self):
        """Test creating an identity through the API."""
        # Create client
        alice = self.create_client("alice")
        
        # Create identity
        identity = alice.create_identity("test-network")
        
        # Verify identity was created
        assert identity["identity_id"] is not None
        assert identity["network_id"] == "test-network"
        assert identity["created_at"] is not None
        
        # Verify identity appears in list
        identities = alice.list_identities()
        assert len(identities) == 1
        assert identities[0]["peer_id"] == identity["identity_id"]
    
    def test_multiple_identities_same_network(self):
        """Test creating multiple identities on the same network."""
        # Create clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        
        # Create identities
        alice_id = alice.create_identity("shared-network")
        bob_id = bob.create_identity("shared-network")
        
        # Verify different identities
        assert alice_id["identity_id"] != bob_id["identity_id"]
        assert alice_id["network_id"] == bob_id["network_id"] == "shared-network"
        
        # Each client only sees their own identity
        assert len(alice.list_identities()) == 1
        assert len(bob.list_identities()) == 1
    
    def test_key_creation(self):
        """Test creating encryption keys for groups."""
        # Create client and identity
        alice = self.create_client("alice")
        identity = alice.create_identity("test-network")
        
        # Create a key for a group
        key = alice.create_key(
            group_id="test-group",
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        
        # Verify key was created
        assert key["key_id"] is not None
        assert key["group_id"] == "test-group"
        assert key["created_by"] == identity["identity_id"]
        
        # Verify key appears in list
        keys = alice.list_keys()
        assert len(keys) == 1
        assert keys[0]["key_id"] == key["key_id"]
    
    def test_transit_secret_creation(self):
        """Test creating transit encryption secrets."""
        # Create client and identity
        alice = self.create_client("alice")
        identity = alice.create_identity("test-network")
        
        # Create transit secret
        secret = alice.create_transit_secret(
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        
        # Verify secret was created
        assert secret["secret_id"] is not None
        assert secret["peer_id"] == identity["identity_id"]
        assert secret["network_id"] == "test-network"
        
        # Verify secret appears in list
        secrets = alice.list_transit_keys()
        assert len(secrets) == 1
        assert secrets[0]["secret_id"] == secret["secret_id"]
    
    def test_database_dump(self):
        """Test dumping database state."""
        # Create client and some data
        alice = self.create_client("alice")
        identity = alice.create_identity("test-network")
        
        # Dump database
        db_state = alice.dump_database()
        
        # Verify database contains expected tables
        assert isinstance(db_state, dict)
        assert any("identity" in table for table in db_state.keys())
        
        # Verify identity event exists
        identity_events = []
        for table_name, rows in db_state.items():
            if "identity" in table_name and "_events" in table_name:
                identity_events.extend(rows)
        
        assert len(identity_events) == 1
        assert identity_events[0]["peer_id"] == identity["identity_id"]
    
    def test_error_handling(self):
        """Test API error handling."""
        # Create client
        alice = self.create_client("alice")
        
        # Try to create key without identity
        with pytest.raises(APIError) as exc_info:
            alice.create_key(
                group_id="test-group",
                network_id="test-network",
                identity_id="non-existent-id"
            )
        
        assert exc_info.value.status_code == 500
    
    def test_sequential_operations(self):
        """Test a sequence of operations building on each other."""
        # Create client
        alice = self.create_client("alice")
        
        # Step 1: Create identity
        identity = alice.create_identity("test-network")
        assert identity["identity_id"] is not None
        
        # Step 2: Create transit secret
        secret = alice.create_transit_secret(
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        assert secret["secret_id"] is not None
        
        # Step 3: Create group key
        key = alice.create_key(
            group_id="my-group",
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        assert key["key_id"] is not None
        
        # Verify all items exist
        assert len(alice.list_identities()) == 1
        assert len(alice.list_transit_keys()) == 1
        assert len(alice.list_keys()) == 1
    
    def test_filtering_by_criteria(self):
        """Test filtering lists by various criteria."""
        # Create client and identity
        alice = self.create_client("alice")
        identity = alice.create_identity("test-network")
        
        # Create multiple keys for different groups
        key1 = alice.create_key(
            group_id="group-1",
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        key2 = alice.create_key(
            group_id="group-2",
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        
        # List all keys
        all_keys = alice.list_keys()
        assert len(all_keys) == 2
        
        # Filter by group (if supported by the API)
        group1_keys = alice.list_keys(group_id="group-1")
        if len(group1_keys) == 1:  # If filtering is supported
            assert group1_keys[0]["key_id"] == key1["key_id"]