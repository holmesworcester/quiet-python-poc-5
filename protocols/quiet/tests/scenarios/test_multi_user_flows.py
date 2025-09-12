"""
Multi-user scenario tests for Quiet protocol.
"""
import pytest
from .base import ScenarioTestBase


class TestMultiUserFlows(ScenarioTestBase):
    """Test multi-user interactions with real API calls."""
    
    def test_shared_group_key_distribution(self):
        """Test distributing encryption keys within a group."""
        # Create two clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        
        # Create identities
        alice_id = alice.create_identity("test-network")
        bob_id = bob.create_identity("test-network")
        
        # Alice creates a group key
        alice_key = alice.create_key(
            group_id="shared-group",
            network_id="test-network",
            identity_id=alice_id["identity_id"]
        )
        
        # Get the key event from Alice's database
        alice_db = alice.dump_database()
        key_event = None
        for table_name, rows in alice_db.items():
            if "key_events" in table_name:
                for row in rows:
                    if row.get("key_id") == alice_key["key_id"]:
                        key_event = row
                        break
        
        assert key_event is not None, "Key event not found in Alice's database"
        
        # Share the key event with Bob
        self.share_event("alice", "bob", key_event)
        
        # Bob should now have the key
        bob_keys = bob.list_keys()
        assert len(bob_keys) == 1
        assert bob_keys[0]["key_id"] == alice_key["key_id"]
        assert bob_keys[0]["created_by"] == alice_id["identity_id"]
    
    def test_transit_secret_exchange(self):
        """Test exchanging transit secrets between peers."""
        # Create two clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        
        # Create identities
        alice_id = alice.create_identity("test-network")
        bob_id = bob.create_identity("test-network")
        
        # Both create transit secrets
        alice_secret = alice.create_transit_secret(
            network_id="test-network",
            identity_id=alice_id["identity_id"]
        )
        bob_secret = bob.create_transit_secret(
            network_id="test-network",
            identity_id=bob_id["identity_id"]
        )
        
        # Get transit secret events from databases
        alice_db = alice.dump_database()
        bob_db = bob.dump_database()
        
        alice_secret_event = None
        bob_secret_event = None
        
        for table_name, rows in alice_db.items():
            if "transit_secret_events" in table_name:
                for row in rows:
                    if row.get("peer_id") == alice_id["identity_id"]:
                        alice_secret_event = row
                        break
        
        for table_name, rows in bob_db.items():
            if "transit_secret_events" in table_name:
                for row in rows:
                    if row.get("peer_id") == bob_id["identity_id"]:
                        bob_secret_event = row
                        break
        
        # Exchange secrets
        if alice_secret_event:
            self.share_event("alice", "bob", alice_secret_event)
        if bob_secret_event:
            self.share_event("bob", "alice", bob_secret_event)
        
        # Both should now have both secrets
        alice_secrets = alice.list_transit_keys()
        bob_secrets = bob.list_transit_keys()
        
        # Each should have their own and the other's secret
        assert len(alice_secrets) >= 2
        assert len(bob_secrets) >= 2
    
    def test_event_dependencies(self):
        """Test that events with dependencies are handled correctly."""
        # Create three clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        charlie = self.create_client("charlie")
        
        # Create identities
        alice_id = alice.create_identity("test-network")
        bob_id = bob.create_identity("test-network")
        charlie_id = charlie.create_identity("test-network")
        
        # Alice creates a key
        alice_key = alice.create_key(
            group_id="test-group",
            network_id="test-network",
            identity_id=alice_id["identity_id"]
        )
        
        # Get Alice's identity and key events
        alice_db = alice.dump_database()
        alice_identity_event = None
        alice_key_event = None
        
        for table_name, rows in alice_db.items():
            if "identity_events" in table_name:
                for row in rows:
                    if row.get("peer_id") == alice_id["identity_id"]:
                        alice_identity_event = row
            elif "key_events" in table_name:
                for row in rows:
                    if row.get("key_id") == alice_key["key_id"]:
                        alice_key_event = row
        
        # Share key with Bob (without identity) - should be pending
        if alice_key_event:
            self.share_event("alice", "bob", alice_key_event)
        
        # Bob shouldn't see the key yet (missing dependency)
        bob_keys_before = bob.list_keys()
        key_count_before = len([k for k in bob_keys_before if k.get("key_id") == alice_key["key_id"]])
        
        # Now share Alice's identity
        if alice_identity_event:
            self.share_event("alice", "bob", alice_identity_event)
        
        # Bob should now see the key (dependency resolved)
        bob_keys_after = bob.list_keys()
        key_count_after = len([k for k in bob_keys_after if k.get("key_id") == alice_key["key_id"]])
        
        # The key should appear after identity is shared
        assert key_count_after > key_count_before
    
    def test_concurrent_operations(self):
        """Test concurrent operations from multiple users."""
        # Create three clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        charlie = self.create_client("charlie")
        
        # All create identities on the same network
        alice_id = alice.create_identity("concurrent-network")
        bob_id = bob.create_identity("concurrent-network")
        charlie_id = charlie.create_identity("concurrent-network")
        
        # All create keys for the same group
        alice_key = alice.create_key(
            group_id="shared-group",
            network_id="concurrent-network",
            identity_id=alice_id["identity_id"]
        )
        bob_key = bob.create_key(
            group_id="shared-group",
            network_id="concurrent-network",
            identity_id=bob_id["identity_id"]
        )
        charlie_key = charlie.create_key(
            group_id="shared-group",
            network_id="concurrent-network",
            identity_id=charlie_id["identity_id"]
        )
        
        # Each should have their own key
        assert len(alice.list_keys()) == 1
        assert len(bob.list_keys()) == 1
        assert len(charlie.list_keys()) == 1
        
        # Keys should be different
        assert alice_key["key_id"] != bob_key["key_id"]
        assert bob_key["key_id"] != charlie_key["key_id"]
        assert alice_key["key_id"] != charlie_key["key_id"]
    
    def test_network_isolation(self):
        """Test that different networks are properly isolated."""
        # Create two clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        
        # Create identities on different networks
        alice_id = alice.create_identity("network-a")
        bob_id = bob.create_identity("network-b")
        
        # Create keys on their respective networks
        alice_key = alice.create_key(
            group_id="group-1",
            network_id="network-a",
            identity_id=alice_id["identity_id"]
        )
        bob_key = bob.create_key(
            group_id="group-1",
            network_id="network-b",
            identity_id=bob_id["identity_id"]
        )
        
        # Get events
        alice_db = alice.dump_database()
        bob_db = bob.dump_database()
        
        alice_key_event = None
        for table_name, rows in alice_db.items():
            if "key_events" in table_name:
                for row in rows:
                    if row.get("key_id") == alice_key["key_id"]:
                        alice_key_event = row
                        break
        
        # Try to share Alice's key with Bob (different network)
        if alice_key_event:
            self.share_event("alice", "bob", alice_key_event)
        
        # Bob should not have Alice's key (different network)
        bob_keys = bob.list_keys()
        alice_keys_in_bob = [k for k in bob_keys if k.get("created_by") == alice_id["identity_id"]]
        
        # Keys from different networks should be isolated
        assert len(alice_keys_in_bob) == 0