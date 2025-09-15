"""
Tests for multi-identity chat scenarios.

These tests use the APIClient directly, mirroring production usage from demo.py.
"""
import tempfile
from pathlib import Path
from core.api import APIClient


class TestMultiIdentityChat:
    """Test multiple identities chatting in the same database."""

    def test_two_identities_separate_networks(self):
        """Test that two identities with separate networks don't see each other's messages."""
        # Setup API client with temporary database
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(
                protocol_dir=Path(__file__).parent.parent.parent,  # protocols/quiet
                reset_db=True,
                db_path=Path(tmp.name)
            )

            # Create two identities
            alice_result = api.execute_operation('create_identity', {'name': 'Alice'})
            alice_id = alice_result['ids']['identity']

            bob_result = api.execute_operation('create_identity', {'name': 'Bob'})
            bob_id = bob_result['ids']['identity']

            # Each creates their own network
            alice_network = api.execute_operation('create_network', {
                'identity_id': alice_id,
                'name': 'Alice Private Network',
                'username': 'Alice'
            })
            alice_channel_id = alice_network['ids']['channel']

            bob_network = api.execute_operation('create_network', {
                'identity_id': bob_id,
                'name': 'Bob Private Network',
                'username': 'Bob'
            })
            bob_channel_id = bob_network['ids']['channel']

            # Each sends messages in their own network
            alice_msg = api.execute_operation('create_message', {
                'identity_id': alice_id,
                'channel_id': alice_channel_id,
                'content': "Alice's secret message"
            })

            bob_msg = api.execute_operation('create_message', {
                'identity_id': bob_id,
                'channel_id': bob_channel_id,
                'content': "Bob's confidential message"
            })

            # Query messages (using API queries with identity_id)
            alice_messages = api.execute_operation('get_messages', {
                'identity_id': alice_id,
                'channel_id': alice_channel_id
            })
            alice_contents = [msg['content'] for msg in alice_messages]
            assert "Alice's secret message" in alice_contents
            assert "Bob's confidential message" not in alice_contents

            bob_messages = api.execute_operation('get_messages', {
                'identity_id': bob_id,
                'channel_id': bob_channel_id
            })
            bob_contents = [msg['content'] for msg in bob_messages]
            assert "Bob's confidential message" in bob_contents
            assert "Alice's secret message" not in bob_contents


    def test_three_identities_with_invites(self):
        """Test three identities joining and chatting via invite system."""
        # Setup API client with temporary database
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(
                protocol_dir=Path(__file__).parent.parent.parent,  # protocols/quiet
                reset_db=True,
                db_path=Path(tmp.name)
            )

            # Alice creates an identity and network
            alice_result = api.execute_operation('create_identity', {'name': 'Alice'})
            alice_id = alice_result['ids']['identity']

            network_result = api.execute_operation('create_network', {
                'identity_id': alice_id,
                'name': 'Group Chat Network',
                'username': 'Alice'
            })
            network_id = network_result['ids']['network']
            group_id = network_result['ids']['group']
            channel_id = network_result['ids']['channel']

            # Alice creates an invite link
            invite_result = api.execute_operation('create_invite', {
                'identity_id': alice_id,
                'network_id': network_id,
                'group_id': group_id
            })

            # Get the invite link from the API response
            invite_link = invite_result['data']['invite_link']

            # Bob joins using the invite link
            bob_join = api.execute_operation('join_as_user', {
            'invite_link': invite_link,
            'name': 'Bob'
            })
            bob_id = bob_join.get('ids', {}).get('identity', bob_join.get('ids', {}).get('peer'))
            assert bob_id, "Bob failed to join the network"

            # Charlie joins using the same invite link
            charlie_join = api.execute_operation('join_as_user', {
            'invite_link': invite_link,
            'name': 'Charlie'
            })
            charlie_id = charlie_join.get('ids', {}).get('identity', charlie_join.get('ids', {}).get('peer'))
            assert charlie_id, "Charlie failed to join the network"

            # Everyone sends messages
            alice_msg = api.execute_operation('create_message', {
            'identity_id': alice_id,
            'channel_id': channel_id,
            'content': 'Welcome everyone!'
            })

            bob_msg = api.execute_operation('create_message', {
                'identity_id': bob_id,
                'channel_id': channel_id,
                'content': 'Thanks for the invite!'
            })

            charlie_msg = api.execute_operation('create_message', {
                'identity_id': charlie_id,
                'channel_id': channel_id,
                'content': 'Happy to be here!'
            })

            # Check that each identity can see all messages
            expected_messages = ['Welcome everyone!', 'Thanks for the invite!', 'Happy to be here!']

            # Alice sees all messages
            alice_messages = api.execute_operation('get_messages', {
                'identity_id': alice_id,
                'channel_id': channel_id
            })
            alice_contents = [msg['content'] for msg in alice_messages]
            for msg in expected_messages:
                assert msg in alice_contents, f"Alice can't see message: {msg}"

            # Bob sees all messages
            bob_messages = api.execute_operation('get_messages', {
                'identity_id': bob_id,
                'channel_id': channel_id
            })
            bob_contents = [msg['content'] for msg in bob_messages]
            for msg in expected_messages:
                assert msg in bob_contents, f"Bob can't see message: {msg}"

            # Charlie sees all messages
            charlie_messages = api.execute_operation('get_messages', {
                'identity_id': charlie_id,
                'channel_id': channel_id
            })
            charlie_contents = [msg['content'] for msg in charlie_messages]
            for msg in expected_messages:
                assert msg in charlie_contents, f"Charlie can't see message: {msg}"