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

            # Use identity.create_as_user to bootstrap each user's network
            alice_boot = api.execute_operation('identity.create_as_user', {
                'name': 'Alice',
                'network_name': 'Alice Private Network',
                'group_name': 'Alice Group',
                'channel_name': 'alice-channel'
            })
            alice_id = alice_boot['ids']['identity']
            alice_peer_id = alice_boot['ids']['peer']
            alice_network_id = alice_boot['ids']['network']
            alice_group_id = alice_boot['ids']['group']
            alice_channel_id = alice_boot['ids']['channel']

            bob_boot = api.execute_operation('identity.create_as_user', {
                'name': 'Bob',
                'network_name': 'Bob Private Network',
                'group_name': 'Bob Group',
                'channel_name': 'bob-channel'
            })
            bob_id = bob_boot['ids']['identity']
            bob_peer_id = bob_boot['ids']['peer']
            bob_network_id = bob_boot['ids']['network']
            bob_group_id = bob_boot['ids']['group']
            bob_channel_id = bob_boot['ids']['channel']

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

            # Tick scheduler to trigger any sync jobs (though they're in separate networks)
            jobs_triggered = api.tick_scheduler()
            print(f"Jobs triggered after messages: {jobs_triggered}")

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
            alice_result = api.execute_operation('identity.create', {'name': 'Alice'})
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

            # Verify Alice has a user entry (should be created automatically)
            alice_users = api.execute_operation('user.get', {
                'identity_id': alice_id,
                'network_id': network_id
            })
            alice_user_ids = [u.get('user_id') for u in alice_users]
            # Note: Alice might not have a user entry yet since she hasn't explicitly created one
            print(f"Alice users: {alice_user_ids}")

            # Alice creates an invite link
            invite_result = api.execute_operation('invite.create', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'group_id': group_id
            })

            # Get the invite link from the API response
            invite_link = invite_result['data']['invite_link']

            # Initial scheduler tick to set up any background jobs
            jobs_triggered = api.tick_scheduler()
            print(f"Initial jobs triggered: {jobs_triggered}")

            # Bob joins using the invite link (creates identity, peer, and user all at once)
            bob_join = api.execute_operation('user.join_as_user', {
                'invite_link': invite_link,
                'name': 'Bob'
            })
            bob_id = bob_join['ids']['identity']
            bob_peer_id = bob_join['ids']['peer']
            assert 'user' in bob_join['ids'], f"Bob user not created by join. Got: {bob_join['ids']}"

            # Charlie joins using the same invite link (creates identity, peer, and user all at once)
            charlie_join = api.execute_operation('user.join_as_user', {
                'invite_link': invite_link,
                'name': 'Charlie'
            })
            charlie_id = charlie_join['ids']['identity']
            charlie_peer_id = charlie_join['ids']['peer']
            assert 'user' in charlie_join['ids'], f"Charlie user not created by join. Got: {charlie_join['ids']}"

            # Verify all users are in the network (check each identity separately)
            bob_users = api.execute_operation('user.get', {
                'identity_id': bob_id,
                'network_id': network_id
            })
            bob_user_ids = [u.get('user_id') for u in bob_users]

            charlie_users = api.execute_operation('user.get', {
                'identity_id': charlie_id,
                'network_id': network_id
            })
            charlie_user_ids = [u.get('user_id') for u in charlie_users]

            print(f"Bob users: {bob_user_ids}")
            print(f"Charlie users: {charlie_user_ids}")

            # Only Bob and Charlie should have user entries from join
            assert len(bob_users) > 0, f"Bob has no user entries"
            assert len(charlie_users) > 0, f"Charlie has no user entries"

            # Everyone sends messages
            alice_msg = api.execute_operation('message.create', {
                'peer_id': alice_peer_id,
                'channel_id': channel_id,
                'content': 'Welcome everyone!'
            })

            # Tick scheduler after Alice's message to potentially sync to others
            jobs_triggered = api.tick_scheduler()
            print(f"Jobs triggered after Alice's message: {jobs_triggered}")

            bob_msg = api.execute_operation('message.create', {
                'peer_id': bob_peer_id,
                'channel_id': channel_id,
                'content': 'Thanks for the invite!'
            })

            # Tick scheduler after Bob's message
            jobs_triggered = api.tick_scheduler()
            print(f"Jobs triggered after Bob's message: {jobs_triggered}")

            charlie_msg = api.execute_operation('message.create', {
                'peer_id': charlie_peer_id,
                'channel_id': channel_id,
                'content': 'Happy to be here!'
            })

            # Final tick to ensure all messages have a chance to sync
            jobs_triggered = api.tick_scheduler()
            print(f"Jobs triggered after Charlie's message: {jobs_triggered}")

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
