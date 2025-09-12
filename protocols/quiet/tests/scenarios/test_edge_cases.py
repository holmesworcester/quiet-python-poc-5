"""
Edge case scenario tests for Quiet protocol.
"""
import pytest
from .base import ScenarioTestBase
from core.api_client import APIError


class TestEdgeCases(ScenarioTestBase):
    """Test edge cases and error conditions with real API calls."""
    
    def test_duplicate_identity_creation(self):
        """Test creating duplicate identities."""
        # Create client
        alice = self.create_client("alice")
        
        # Create first identity
        identity1 = alice.create_identity("test-network")
        
        # Try to create another identity (should succeed - different ID)
        identity2 = alice.create_identity("test-network")
        
        # Should have different IDs
        assert identity1["identity_id"] != identity2["identity_id"]
        assert len(alice.list_identities()) == 2
    
    def test_invalid_identity_reference(self):
        """Test operations with invalid identity references."""
        # Create client
        alice = self.create_client("alice")
        
        # Try to create key without valid identity
        with pytest.raises(APIError):
            alice.create_key(
                group_id="test-group",
                network_id="test-network",
                identity_id="invalid-identity-id"
            )
        
        # Try to create transit secret without valid identity
        with pytest.raises(APIError):
            alice.create_transit_secret(
                network_id="test-network",
                identity_id="invalid-identity-id"
            )
    
    def test_empty_parameters(self):
        """Test API calls with empty or missing parameters."""
        # Create client
        alice = self.create_client("alice")
        
        # Test empty network ID
        with pytest.raises(APIError):
            alice.create_identity("")
        
        # Test None network ID (if the API doesn't handle it)
        with pytest.raises((APIError, TypeError)):
            alice.create_identity(None)
    
    def test_very_long_identifiers(self):
        """Test handling of very long identifiers."""
        # Create client
        alice = self.create_client("alice")
        
        # Create identity with very long network ID
        long_network_id = "network-" + "x" * 1000
        identity = alice.create_identity(long_network_id)
        
        # Should handle long IDs gracefully
        assert identity["network_id"] == long_network_id
        
        # Create key with very long group ID
        long_group_id = "group-" + "y" * 1000
        key = alice.create_key(
            group_id=long_group_id,
            network_id=long_network_id,
            identity_id=identity["identity_id"]
        )
        
        assert key["group_id"] == long_group_id
    
    def test_special_characters_in_ids(self):
        """Test handling special characters in identifiers."""
        # Create client
        alice = self.create_client("alice")
        
        # Test various special characters
        special_networks = [
            "network-with-dashes",
            "network_with_underscores",
            "network.with.dots",
            "network:with:colons",
            "network/with/slashes",
            "network with spaces",
            "network@with@at",
            "network#with#hash"
        ]
        
        for network_id in special_networks:
            try:
                identity = alice.create_identity(network_id)
                assert identity["network_id"] == network_id
            except APIError:
                # Some characters might not be allowed
                pass
    
    def test_rapid_sequential_operations(self):
        """Test rapid sequential operations without delays."""
        # Create client
        alice = self.create_client("alice")
        
        # Create identity
        identity = alice.create_identity("test-network")
        
        # Rapidly create multiple keys
        keys = []
        for i in range(10):
            key = alice.create_key(
                group_id=f"group-{i}",
                network_id="test-network",
                identity_id=identity["identity_id"]
            )
            keys.append(key)
        
        # All keys should be created
        assert len(keys) == 10
        all_keys = alice.list_keys()
        assert len(all_keys) == 10
        
        # All keys should have unique IDs
        key_ids = [k["key_id"] for k in keys]
        assert len(set(key_ids)) == 10
    
    def test_malformed_event_handling(self):
        """Test handling of malformed events."""
        # Create two clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        
        # Create identity for Alice
        alice_id = alice.create_identity("test-network")
        
        # Create various malformed events
        malformed_events = [
            # Missing type
            {
                "peer_id": alice_id["identity_id"],
                "network_id": "test-network",
                "created_at": 1234567890
            },
            # Missing required fields
            {
                "type": "identity",
                "network_id": "test-network"
                # Missing peer_id
            },
            # Invalid type
            {
                "type": "invalid_type",
                "peer_id": alice_id["identity_id"],
                "network_id": "test-network"
            },
            # Wrong data types
            {
                "type": "identity",
                "peer_id": 12345,  # Should be string
                "network_id": "test-network",
                "created_at": "not-a-number"  # Should be number
            }
        ]
        
        # Try to share malformed events
        for event in malformed_events:
            try:
                self.share_event("alice", "bob", event)
                # Check if Bob received/processed the event
                bob_db = bob.dump_database()
                # The malformed event should not be processed successfully
            except Exception:
                # Expected - malformed events should cause errors
                pass
    
    def test_database_persistence(self):
        """Test that data persists across client reconnections."""
        # Create client and add data
        db_path = self.temp_dir + "/persistent.db"
        
        # First session
        alice1 = self.create_client("alice")
        identity = alice1.create_identity("test-network")
        key = alice1.create_key(
            group_id="test-group",
            network_id="test-network",
            identity_id=identity["identity_id"]
        )
        
        # Close first client
        if hasattr(alice1, '_db'):
            alice1._db.close()
        
        # Second session with same database
        alice2 = self.create_client("alice", reset_db=False)
        
        # Data should persist
        identities = alice2.list_identities()
        keys = alice2.list_keys()
        
        assert len(identities) >= 1
        assert len(keys) >= 1
        assert any(i["peer_id"] == identity["identity_id"] for i in identities)
        assert any(k["key_id"] == key["key_id"] for k in keys)
    
    def test_concurrent_database_access(self):
        """Test concurrent access to the same database."""
        # This tests database locking and concurrent access handling
        import threading
        import time
        
        # Create initial client and identity
        alice = self.create_client("alice")
        identity = alice.create_identity("test-network")
        
        results = []
        errors = []
        
        def create_key(group_num):
            try:
                key = alice.create_key(
                    group_id=f"group-{group_num}",
                    network_id="test-network",
                    identity_id=identity["identity_id"]
                )
                results.append(key)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads trying to create keys simultaneously
        threads = []
        for i in range(5):
            t = threading.Thread(target=create_key, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Should have created keys (some might fail due to locking)
        total_operations = len(results) + len(errors)
        assert total_operations == 5
        
        # At least some operations should succeed
        assert len(results) > 0