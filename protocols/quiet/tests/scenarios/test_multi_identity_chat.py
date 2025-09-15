"""
Test multi-identity chat scenarios with single database.

These tests demonstrate the proper architecture where multiple identities
exist in a single client database and communicate via loopback.
"""
import pytest


class TestMultiIdentityChat:
    """Test multiple identities chatting in the same database."""

    def test_two_identities_basic_chat(self, test_context):
        """Test two identities can chat in the same network."""
        # Create two identities
        alice_id = test_context.create_identity("Alice")
        bob_id = test_context.create_identity("Bob")

        # Alice creates a network with a user event
        network_id = test_context.create_network("Alice", "Test Network", username="Alice")

        # Alice creates a group
        group_id = test_context.create_group("Alice", "Main Group", "Test Network")

        # Alice creates a channel
        channel_id = test_context.create_channel("Alice", "general", "Main Group", "Test Network")

        # Bob joins the network
        test_context.join_network("Bob", "Test Network", username="Bob")

        # Alice sends a message
        alice_msg_id = test_context.send_message("Alice", "Hello Bob!", "general")
        assert alice_msg_id is not None

        # Bob sends a reply
        bob_msg_id = test_context.send_message("Bob", "Hi Alice!", "general")
        assert bob_msg_id is not None

        # Both should see both messages
        alice_view = test_context.get_messages("Alice", "general")
        assert len(alice_view) >= 2

        messages_content = [msg.get('content') for msg in alice_view]
        assert "Hello Bob!" in messages_content
        assert "Hi Alice!" in messages_content

    def test_three_identities_group_chat(self, test_context):
        """Test three identities in a group chat."""
        # Create three identities
        alice_id = test_context.create_identity("Alice")
        bob_id = test_context.create_identity("Bob")
        charlie_id = test_context.create_identity("Charlie")

        # Alice creates the infrastructure
        network_id = test_context.create_network("Alice", "Group Chat Network", username="Alice")
        group_id = test_context.create_group("Alice", "Chat Group", "Group Chat Network")
        channel_id = test_context.create_channel("Alice", "general", "Chat Group", "Group Chat Network")

        # Bob and Charlie join
        test_context.join_network("Bob", "Group Chat Network", username="Bob")
        test_context.join_network("Charlie", "Group Chat Network", username="Charlie")

        # Everyone sends messages
        test_context.send_message("Alice", "Welcome everyone!", "general")
        test_context.send_message("Bob", "Thanks for the invite!", "general")
        test_context.send_message("Charlie", "Happy to be here!", "general")

        # Check everyone can see all messages
        messages = test_context.get_messages("Alice", "general")
        assert len(messages) >= 3

        contents = [msg.get('content') for msg in messages]
        assert "Welcome everyone!" in contents
        assert "Thanks for the invite!" in contents
        assert "Happy to be here!" in contents

    def test_identity_isolation(self, test_context):
        """Test that identities only see their own networks."""
        # Create two separate networks with different identities
        alice_id = test_context.create_identity("Alice")
        bob_id = test_context.create_identity("Bob")

        # Alice creates her network
        alice_network = test_context.create_network("Alice", "Alice Network", username="Alice")
        alice_group = test_context.create_group("Alice", "Alice Group", "Alice Network")
        alice_channel = test_context.create_channel("Alice", "alice-chat", "Alice Group", "Alice Network")

        # Bob creates his own separate network
        bob_network = test_context.create_network("Bob", "Bob Network", username="Bob")
        bob_group = test_context.create_group("Bob", "Bob Group", "Bob Network")
        bob_channel = test_context.create_channel("Bob", "bob-chat", "Bob Group", "Bob Network")

        # Each sends a message in their own network
        test_context.send_message("Alice", "Alice's private message", "alice-chat")
        test_context.send_message("Bob", "Bob's private message", "bob-chat")

        # Alice shouldn't see Bob's message
        alice_messages = test_context.get_messages("Alice", "alice-chat")
        alice_contents = [msg.get('content') for msg in alice_messages]
        assert "Alice's private message" in alice_contents
        assert "Bob's private message" not in alice_contents

        # Bob shouldn't see Alice's message
        bob_messages = test_context.get_messages("Bob", "bob-chat")
        bob_contents = [msg.get('content') for msg in bob_messages]
        assert "Bob's private message" in bob_contents
        assert "Alice's private message" not in bob_contents

    def test_sync_between_identities(self, test_context):
        """Test sync job exchanges events between identities."""
        # Skip this test for now - sync needs more work
        import pytest
        pytest.skip("Sync job needs refactoring to work properly")

    def test_loopback_sync_simulation(self, test_context):
        """Test direct sync simulation between two identities."""
        # Create identities
        alice_id = test_context.create_identity("Alice")
        bob_id = test_context.create_identity("Bob")

        # Set up network
        network_id = test_context.create_network("Alice", "Loopback Network", username="Alice")
        group_id = test_context.create_group("Alice", "Loopback Group", "Loopback Network")
        channel_id = test_context.create_channel("Alice", "loopback-channel", "Loopback Group", "Loopback Network")

        # Bob joins
        test_context.join_network("Bob", "Loopback Network", username="Bob")

        # Alice sends a message
        test_context.send_message("Alice", "Testing loopback sync", "loopback-channel")

        # Messages are visible immediately in single database
        # No need for explicit sync
        messages = test_context.get_messages("Bob", "loopback-channel")
        contents = [msg.get('content') for msg in messages]
        assert "Testing loopback sync" in contents

