"""
Integration tests for multi-event commands with dependencies.

Tests that commands creating multiple related events work correctly,
with proper resolution of references between events.
"""
import tempfile
import os
import pytest
from pathlib import Path
from core.api import APIClient
from core.db import get_connection, init_database
from core.pipeline import PipelineRunner


class TestMultiEventCommands:
    """Test commands that create multiple events with dependencies."""

    def test_join_as_user_creates_all_events(self):
        """Test that join_as_user creates identity, peer, and user events correctly."""
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(
                protocol_dir=Path(__file__).parent.parent.parent,
                reset_db=True,
                db_path=Path(tmp.name)
            )

            # First, create Alice with a network and group
            alice_result = api.execute_operation('core.identity_create', {'name': 'Alice'})
            alice_id = alice_result['ids']['identity']

            alice_peer = api.execute_operation('peer.create_peer', {
                'identity_id': alice_id,
                'username': 'Alice'
            })
            alice_peer_id = alice_peer['ids']['peer']

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

            # Alice creates an invite
            invite = api.execute_operation('invite.create_invite', {
                'peer_id': alice_peer_id,
                'network_id': network_id,
                'group_id': group_id
            })
            invite_link = invite['data']['invite_link']

            # Now Bob joins using the invite link - this should create:
            # 1. Identity (stored in core_identities)
            # 2. Peer event
            # 3. User event
            bob_result = api.execute_operation('user.join_as_user', {
                'invite_link': invite_link,
                'name': 'Bob'
            })

            # Verify we got all the IDs back
            assert 'identity' in bob_result['ids'], f"Identity not created. Got: {bob_result['ids']}"
            assert 'peer' in bob_result['ids'], f"Peer not created. Got: {bob_result['ids']}"
            assert 'user' in bob_result['ids'], f"User not created. Got: {bob_result['ids']}"

            bob_identity_id = bob_result['ids']['identity']
            bob_peer_id = bob_result['ids']['peer']
            bob_user_id = bob_result['ids']['user']

            # Verify the identity was created in core_identities
            db = get_connection(tmp.name)
            cursor = db.execute("""
                SELECT identity_id, name FROM core_identities
                WHERE identity_id = ?
            """, (bob_identity_id,))
            identity_row = cursor.fetchone()
            assert identity_row is not None, "Identity not found in core_identities"
            assert identity_row['name'] == 'Bob', f"Identity name mismatch: {identity_row['name']}"

            # Verify the peer event was created
            cursor = db.execute("""
                SELECT peer_id, identity_id FROM peers
                WHERE peer_id = ?
            """, (bob_peer_id,))
            peer_row = cursor.fetchone()
            assert peer_row is not None, "Peer not found in peers table"
            assert peer_row['identity_id'] == bob_identity_id, "Peer identity_id mismatch"

            # Verify the user event was created with correct references
            cursor = db.execute("""
                SELECT user_id, peer_id, network_id, name FROM users
                WHERE user_id = ?
            """, (bob_user_id,))
            user_row = cursor.fetchone()
            assert user_row is not None, "User not found in users table"
            assert user_row['peer_id'] == bob_peer_id, f"User peer_id mismatch: {user_row['peer_id']} != {bob_peer_id}"
            assert user_row['network_id'] == network_id, "User network_id mismatch"
            assert user_row['name'] == 'Bob', f"User name mismatch: {user_row['name']}"

            db.close()

    def test_join_resolves_peer_references(self):
        """Test that user event correctly references the peer created in the same command."""
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            # Use direct pipeline to see the event processing
            db = get_connection(tmp.name)
            protocol_dir = Path(__file__).parent.parent.parent
            init_database(db, str(protocol_dir))

            # Create identity for Alice
            db.execute("""
                INSERT INTO core_identities (identity_id, name, private_key, public_key, created_at)
                VALUES ('alice_id', 'Alice', X'1234', X'5678', 1000)
            """)

            # Create peer for Alice
            db.execute("""
                INSERT INTO peers (peer_id, identity_id, public_key, created_at)
                VALUES ('alice_peer_id', 'alice_id', X'5678', 1000)
            """)

            # Create network
            db.execute("""
                INSERT INTO networks (network_id, name, creator_id, created_at)
                VALUES ('network_id', 'Test Network', 'alice_peer_id', 1000)
            """)

            # Create group
            db.execute("""
                INSERT INTO groups (group_id, name, network_id, creator_id, owner_id, created_at)
                VALUES ('group_id', 'Test Group', 'network_id', 'alice_peer_id', 'alice_peer_id', 1000)
            """)

            # Create invite
            db.execute("""
                INSERT INTO invites (invite_id, invite_pubkey, invite_secret, network_id, group_id, inviter_id, created_at)
                VALUES ('invite_id', 'invite_pubkey_test', 'test_secret', 'network_id', 'group_id', 'alice_peer_id', 1000)
            """)
            db.commit()

            # Now simulate Bob joining with placeholders
            from protocols.quiet.events.user.commands import join_as_user

            # Create a mock invite link
            import base64
            import json
            invite_data = {
                'invite_secret': 'test_secret',
                'network_id': 'network_id',
                'group_id': 'group_id'
            }
            invite_json = json.dumps(invite_data)
            invite_b64 = base64.b64encode(invite_json.encode()).decode()
            invite_link = f"quiet://invite/{invite_b64}"

            # Execute join_as_user
            envelopes = join_as_user({
                'invite_link': invite_link,
                'name': 'Bob',
                '_db': db
            })

            # Should return 2 envelopes: peer and user
            assert len(envelopes) == 2, f"Expected 2 envelopes, got {len(envelopes)}"

            peer_envelope = envelopes[0]
            user_envelope = envelopes[1]

            assert peer_envelope['event_type'] == 'peer', f"First envelope should be peer, got {peer_envelope['event_type']}"
            assert user_envelope['event_type'] == 'user', f"Second envelope should be user, got {user_envelope['event_type']}"

            # User envelope should have placeholder reference to peer
            user_event = user_envelope['event_plaintext']
            assert user_event.get('peer_id') == '@generated:peer:0', f"User should reference @generated:peer:0, got {user_event.get('peer_id')}"

            # User envelope dependencies should include the placeholder
            assert '@generated:peer:0' in user_envelope['deps'], f"User deps should include @generated:peer:0, got {user_envelope['deps']}"

            # Run through pipeline to verify resolution
            pipeline = PipelineRunner(db_path=tmp.name, verbose=True)

            # Add request_id to simulate command execution
            for i, env in enumerate(envelopes):
                env['request_id'] = 'test_join_request'

            stored_ids = pipeline.run(
                protocol_dir=str(protocol_dir),
                input_envelopes=envelopes,
                db=db
            )

            # Verify both events were stored
            assert 'peer' in stored_ids, f"Peer event not stored. Got: {stored_ids}"
            assert 'user' in stored_ids, f"User event not stored. Got: {stored_ids}"

            # Verify user event has correct peer_id reference
            cursor = db.execute("""
                SELECT peer_id FROM users WHERE user_id = ?
            """, (stored_ids['user'],))
            user_row = cursor.fetchone()
            assert user_row is not None, "User not found after pipeline"
            assert user_row['peer_id'] == stored_ids['peer'], f"User peer_id should match stored peer: {user_row['peer_id']} != {stored_ids['peer']}"

            db.close()

    def test_group_create_with_member(self):
        """Test that create_group can create both group and member events."""
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(
                protocol_dir=Path(__file__).parent.parent.parent,
                reset_db=True,
                db_path=Path(tmp.name)
            )

            # Create identity and peer first
            identity_result = api.execute_operation('core.identity_create', {'name': 'Alice'})
            identity_id = identity_result['ids']['identity']

            peer_result = api.execute_operation('peer.create_peer', {
                'identity_id': identity_id,
                'username': 'Alice'
            })
            peer_id = peer_result['ids']['peer']

            network_result = api.execute_operation('network.create_network', {
                'peer_id': peer_id,
                'name': 'Test Network'
            })
            network_id = network_result['ids']['network']

            # Create group (should also create member event for creator)
            group_result = api.execute_operation('group.create_group', {
                'peer_id': peer_id,
                'network_id': network_id,
                'name': 'Test Group'
            })

            # Should have created a group
            assert 'group' in group_result['ids'], f"Group not created. Got: {group_result['ids']}"
            group_id = group_result['ids']['group']

            # Verify group was created
            db = get_connection(tmp.name)
            cursor = db.execute("""
                SELECT name, creator_id FROM groups WHERE group_id = ?
            """, (group_id,))
            group_row = cursor.fetchone()
            assert group_row is not None, "Group not found"
            assert group_row['name'] == 'Test Group'
            assert group_row['creator_id'] == peer_id

            db.close()