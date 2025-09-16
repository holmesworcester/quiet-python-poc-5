#!/usr/bin/env python3
"""
Test message sync between multiple identities.
"""
import tempfile
import time
from pathlib import Path
from core.api import APIClient


def test_message_sync():
    """Test that messages sync between identities in the same group."""
    with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
        api = APIClient(
            protocol_dir=Path('protocols/quiet'),
            reset_db=True,
            db_path=Path(tmp.name)
        )

        print("Creating Alice...")
        # Create Alice
        alice_result = api.execute_operation('core.identity_create', {'name': 'Alice'})
        alice_id = alice_result['ids']['identity']

        alice_peer = api.execute_operation('peer.create_peer', {
            'identity_id': alice_id,
            'username': 'Alice'
        })
        alice_peer_id = alice_peer['ids']['peer']

        # Create network and group
        network = api.execute_operation('network.create_network', {
            'peer_id': alice_peer_id,
            'name': 'Test Network'
        })
        network_id = network['ids']['network']

        group = api.execute_operation('group.create_group', {
            'peer_id': alice_peer_id,
            'network_id': network_id,
            'name': 'Test Group'
        })
        group_id = group['ids']['group']

        # Create channel
        channel = api.execute_operation('channel.create_channel', {
            'peer_id': alice_peer_id,
            'group_id': group_id,
            'name': 'general'
        })
        channel_id = channel['ids']['channel']

        print(f"Alice created channel: {channel_id}")

        # Alice sends a message
        msg1 = api.execute_operation('message.create_message', {
            'peer_id': alice_peer_id,
            'channel_id': channel_id,
            'content': 'Hello from Alice!'
        })
        print(f"Alice sent message: {msg1['ids']['message']}")

        # Create Bob
        print("\nCreating Bob...")
        bob_result = api.execute_operation('core.identity_create', {'name': 'Bob'})
        bob_id = bob_result['ids']['identity']

        bob_peer = api.execute_operation('peer.create_peer', {
            'identity_id': bob_id,
            'username': 'Bob'
        })
        bob_peer_id = bob_peer['ids']['peer']

        # Bob creates a user in the same network
        bob_user = api.execute_operation('user.create_user', {
            'peer_id': bob_peer_id,
            'network_id': network_id,
            'name': 'Bob'
        })
        print(f"Bob joined as user: {bob_user['ids']['user']}")

        # Bob sends a message
        msg2 = api.execute_operation('message.create_message', {
            'peer_id': bob_peer_id,
            'channel_id': channel_id,
            'content': 'Hello from Bob!'
        })
        print(f"Bob sent message: {msg2['ids']['message']}")

        # Check messages from both perspectives
        print("\n=== Messages from Alice's perspective ===")
        alice_messages = api.execute_operation('message.get', {
            'channel_id': channel_id,
            'identity_id': alice_id
        })

        for msg in alice_messages if isinstance(alice_messages, list) else alice_messages.get('messages', []):
            print(f"  {msg.get('sender_name', 'Unknown')}: {msg.get('content', '')}")

        print("\n=== Messages from Bob's perspective ===")
        bob_messages = api.execute_operation('message.get', {
            'channel_id': channel_id,
            'identity_id': bob_id
        })

        for msg in bob_messages if isinstance(bob_messages, list) else bob_messages.get('messages', []):
            print(f"  {msg.get('sender_name', 'Unknown')}: {msg.get('content', '')}")

        # Verify both see all messages
        alice_msg_count = len(alice_messages) if isinstance(alice_messages, list) else len(alice_messages.get('messages', []))
        bob_msg_count = len(bob_messages) if isinstance(bob_messages, list) else len(bob_messages.get('messages', []))

        assert alice_msg_count == 2, f"Alice should see 2 messages, got {alice_msg_count}"
        assert bob_msg_count == 2, f"Bob should see 2 messages, got {bob_msg_count}"

        print("\n✅ Message sync works! Both users see all messages.")


if __name__ == '__main__':
    test_message_sync()