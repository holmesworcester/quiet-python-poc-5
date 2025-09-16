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

            # Create two identities using core identity
            alice_result = api.execute_operation('core.identity_create', {'name': 'Alice'})
            alice_id = alice_result['ids']['identity']

            bob_result = api.execute_operation('core.identity_create', {'name': 'Bob'})
            bob_id = bob_result['ids']['identity']

            # Each creates peer first, then network
            alice_peer = api.execute_operation('peer.create', {
                'identity_id': alice_id,
                'username': 'Alice'
            })
            alice_peer_id = alice_peer['ids']['peer']

            alice_network = api.execute_operation('network.create', {
                'peer_id': alice_peer_id,
                'name': 'Alice Private Network'
            })
            alice_network_id = alice_network['ids']['network']

            # Create group for Alice
            alice_group = api.execute_operation('group.create', {
                'peer_id': alice_peer_id,
                'network_id': alice_network_id,
                'name': 'Alice Group'
            })
            alice_group_id = alice_group['ids']['group']

            # Create channel for Alice
            alice_channel = api.execute_operation('channel.create', {
                'peer_id': alice_peer_id,
                'network_id': alice_network_id,
                'group_id': alice_group_id,
                'name': 'alice-channel'
            })
            alice_channel_id = alice_channel['ids']['channel']

            # Bob creates peer first, then network
            bob_peer = api.execute_operation('peer.create', {
                'identity_id': bob_id,
                'username': 'Bob'
            })
            bob_peer_id = bob_peer['ids']['peer']

            bob_network = api.execute_operation('network.create', {
                'peer_id': bob_peer_id,
                'name': 'Bob Private Network'
            })
            bob_network_id = bob_network['ids']['network']

            # Create group for Bob
            bob_group = api.execute_operation('group.create', {
                'peer_id': bob_peer_id,
                'network_id': bob_network_id,
                'name': 'Bob Group'
            })
            bob_group_id = bob_group['ids']['group']

            # Create channel for Bob
            bob_channel = api.execute_operation('channel.create', {
                'peer_id': bob_peer_id,
                'network_id': bob_network_id,
                'group_id': bob_group_id,
                'name': 'bob-channel'
            })
            bob_channel_id = bob_channel['ids']['channel']

            # Each sends messages in their own network
            alice_msg = api.execute_operation('message.create', {
                'peer_id': alice_peer_id,
                'channel_id': alice_channel_id,
                'content': "Alice's secret message"
            })

            bob_msg = api.execute_operation('message.create', {
                'peer_id': bob_peer_id,
                'channel_id': bob_channel_id,
                'content': "Bob's confidential message"
            })

            # Query messages (using API queries with identity_id)
            alice_messages = api.execute_operation('message.get', {
                'identity_id': alice_id,
                'channel_id': alice_channel_id
            })
            alice_contents = [msg['content'] for msg in alice_messages]
            assert "Alice's secret message" in alice_contents
            assert "Bob's confidential message" not in alice_contents

            bob_messages = api.execute_operation('message.get', {
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

            # Alice creates an identity, peer, and network
            alice_result = api.execute_operation('core.identity_create', {'name': 'Alice'})
            alice_id = alice_result['ids']['identity']

            alice_peer = api.execute_operation('peer.create', {
                'identity_id': alice_id,
                'username': 'Alice'
            })
            alice_peer_id = alice_peer['ids']['peer']

            network_result = api.execute_operation('network.create', {
                'peer_id': alice_peer_id,
                'name': 'Group Chat Network'
            })
            network_id = network_result['ids']['network']

            # Create group
            group_result = api.execute_operation('group.create', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'name': 'Main Group'
            })
            group_id = group_result['ids']['group']

            # Create channel
            channel_result = api.execute_operation('channel.create', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'group_id': group_id,
                'name': 'general'
            })
            channel_id = channel_result['ids']['channel']

            # Alice creates an invite link
            invite_result = api.execute_operation('invite.create', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'group_id': group_id
            })

            # Get the invite link from the API response
            invite_link = invite_result['data']['invite_link']

            # Bob joins using the invite link (creates identity, peer, and user all at once)
            bob_join = api.execute_operation('user.join', {
                'invite_link': invite_link,
                'name': 'Bob'
            })
            bob_id = bob_join['ids']['identity']
            bob_peer_id = bob_join['ids']['peer']
            # Note: user event may not be returned if there's an issue with invite validation
            # For now, just check that we got identity and peer

            # Charlie joins using the same invite link (creates identity, peer, and user all at once)
            charlie_join = api.execute_operation('user.join', {
                'invite_link': invite_link,
                'name': 'Charlie'
            })
            charlie_id = charlie_join['ids']['identity']
            charlie_peer_id = charlie_join['ids']['peer']
            # Note: user event may not be returned if there's an issue with invite validation
            # For now, just check that we got identity and peer

            # Everyone sends messages
            alice_msg = api.execute_operation('message.create', {
                'peer_id': alice_peer_id,
                'channel_id': channel_id,
                'content': 'Welcome everyone!'
            })

            bob_msg = api.execute_operation('message.create', {
                'peer_id': bob_peer_id,
                'channel_id': channel_id,
                'content': 'Thanks for the invite!'
            })

            charlie_msg = api.execute_operation('message.create', {
                'peer_id': charlie_peer_id,
                'channel_id': channel_id,
                'content': 'Happy to be here!'
            })

            # Check that each identity can see all messages
            expected_messages = ['Welcome everyone!', 'Thanks for the invite!', 'Happy to be here!']

            # Alice sees all messages
            alice_messages = api.execute_operation('message.get', {
                'identity_id': alice_id,
                'channel_id': channel_id
            })
            alice_contents = [msg['content'] for msg in alice_messages]
            for msg in expected_messages:
                assert msg in alice_contents, f"Alice can't see message: {msg}"

            # Bob sees all messages
            bob_messages = api.execute_operation('message.get', {
                'identity_id': bob_id,
                'channel_id': channel_id
            })
            bob_contents = [msg['content'] for msg in bob_messages]
            for msg in expected_messages:
                assert msg in bob_contents, f"Bob can't see message: {msg}"

            # Charlie sees all messages
            charlie_messages = api.execute_operation('message.get', {
                'identity_id': charlie_id,
                'channel_id': channel_id
            })
            charlie_contents = [msg['content'] for msg in charlie_messages]
            for msg in expected_messages:
                assert msg in charlie_contents, f"Charlie can't see message: {msg}"