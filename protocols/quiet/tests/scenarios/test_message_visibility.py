"""
Test message visibility between users in the same channel.

This test verifies that users can send plain text messages and see each other's messages.
"""
import tempfile
from pathlib import Path
from core.api import APIClient


class TestMessageVisibility:
    """Test that users can send and see each other's messages."""

    def test_simple_message_exchange(self):
        """Test that two users can exchange simple text messages like 'hello world'."""
        # Setup API client with temporary database
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(
                protocol_dir=Path(__file__).parent.parent.parent,  # protocols/quiet
                reset_db=True,
                db_path=Path(tmp.name)
            )

            # Create Alice
            alice_result = api.execute_operation('core_identity_create', {'name': 'Alice'})
            alice_id = alice_result['ids']['identity']

            alice_peer = api.execute_operation('create_peer', {
                'identity_id': alice_id,
                'username': 'Alice'
            })
            alice_peer_id = alice_peer['ids']['peer']

            # Alice creates network
            network = api.execute_operation('create_network', {
                'peer_id': alice_peer_id,
                'name': 'Chat Network'
            })
            network_id = network['ids']['network']

            # Alice creates user event to join network
            alice_user = api.execute_operation('create_user', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'name': 'Alice'
            })

            # Alice creates group and channel
            group = api.execute_operation('create_group', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'name': 'public'
            })
            group_id = group['ids']['group']

            channel = api.execute_operation('create_channel', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'group_id': group_id,
                'name': 'general'
            })
            channel_id = channel['ids']['channel']

            # Alice creates invite for Bob
            invite = api.execute_operation('create_invite', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'group_id': group_id
            })
            invite_link = invite['data']['invite_link']

            # Create Bob
            bob_result = api.execute_operation('core_identity_create', {'name': 'Bob'})
            bob_id = bob_result['ids']['identity']

            bob_peer = api.execute_operation('create_peer', {
                'identity_id': bob_id,
                'username': 'Bob'
            })
            bob_peer_id = bob_peer['ids']['peer']

            # Bob joins with invite
            bob_join = api.execute_operation('join_network_with_invite', {
                'peer_id': bob_peer_id,
                'invite_link': invite_link,
                'username': 'Bob'
            })

            # Alice sends a simple message
            alice_msg1 = api.execute_operation('create_message', {
                'peer_id': alice_peer_id,
                'channel_id': channel_id,
                'content': 'hello world'
            })
            assert alice_msg1 and 'ids' in alice_msg1
            assert 'message' in alice_msg1['ids']

            # Bob sends a simple reply
            bob_msg1 = api.execute_operation('create_message', {
                'peer_id': bob_peer_id,
                'channel_id': channel_id,
                'content': 'hi alice!'
            })
            assert bob_msg1 and 'ids' in bob_msg1
            assert 'message' in bob_msg1['ids']

            # Alice sends another message
            alice_msg2 = api.execute_operation('create_message', {
                'peer_id': alice_peer_id,
                'channel_id': channel_id,
                'content': 'how are you?'
            })

            # Bob sends another reply
            bob_msg2 = api.execute_operation('create_message', {
                'peer_id': bob_peer_id,
                'channel_id': channel_id,
                'content': 'doing great!'
            })

            # Check that Alice can see all messages
            alice_messages = api.execute_operation('get_messages', {
                'identity_id': alice_id,
                'channel_id': channel_id,
                'limit': 10
            })
            alice_contents = [msg['content'] for msg in alice_messages]

            assert 'hello world' in alice_contents, "Alice can't see her own 'hello world' message"
            assert 'hi alice!' in alice_contents, "Alice can't see Bob's 'hi alice!' message"
            assert 'how are you?' in alice_contents, "Alice can't see her own 'how are you?' message"
            assert 'doing great!' in alice_contents, "Alice can't see Bob's 'doing great!' message"

            # Check that Bob can see all messages
            bob_messages = api.execute_operation('get_messages', {
                'identity_id': bob_id,
                'channel_id': channel_id,
                'limit': 10
            })
            bob_contents = [msg['content'] for msg in bob_messages]

            assert 'hello world' in bob_contents, "Bob can't see Alice's 'hello world' message"
            assert 'hi alice!' in bob_contents, "Bob can't see his own 'hi alice!' message"
            assert 'how are you?' in bob_contents, "Bob can't see Alice's 'how are you?' message"
            assert 'doing great!' in bob_contents, "Bob can't see his own 'doing great!' message"

            # Verify message count
            assert len(alice_messages) == 4, f"Expected 4 messages, Alice sees {len(alice_messages)}"
            assert len(bob_messages) == 4, f"Expected 4 messages, Bob sees {len(bob_messages)}"