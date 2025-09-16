"""
Tests for user commands.
"""
import pytest
import base64
import json
import sqlite3
import tempfile
import os
from protocols.quiet.events.user.commands import join_as_user
from core.db import get_connection, init_database


class TestUserCommands:
    """Test user commands."""

    def setup_method(self):
        """Set up test database."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        self.db = get_connection(self.db_path)
        init_database(self.db, 'protocols/quiet')

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_as_user_envelope_structure(self):
        """Test that join_as_user generates correct envelope structure."""
        # Create a test invite link
        invite_data = {
            'invite_secret': 'test_secret_123',
            'network_id': 'test_network',
            'group_id': 'test_group'
        }
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            'invite_link': invite_link,
            'name': 'Alice',
            '_db': self.db
        }

        envelopes = join_as_user(params)

        # Should return 3 envelopes: identity, peer, user
        assert len(envelopes) == 3, "Should create 3 envelopes"

        # Check identity envelope
        identity_env = envelopes[0]
        assert identity_env['event_type'] == 'identity'
        assert identity_env['self_created'] == True
        assert identity_env['validated'] == True
        assert 'event_id' in identity_env  # Pre-computed
        identity_event = identity_env['event_plaintext']
        assert identity_event['type'] == 'identity'
        assert identity_event['name'] == 'Alice'
        assert 'public_key' in identity_event

        # Check peer envelope
        peer_env = envelopes[1]
        assert peer_env['event_type'] == 'peer'
        assert peer_env['self_created'] == True
        peer_event = peer_env['event_plaintext']
        assert peer_event['type'] == 'peer'
        assert 'public_key' in peer_event
        assert peer_event['identity_id'] == identity_env['event_id']

        # Check user envelope
        user_env = envelopes[2]
        assert user_env['event_type'] == 'user'
        assert user_env['self_created'] == True
        user_event = user_env['event_plaintext']
        assert user_event['type'] == 'user'
        assert user_event['peer_id'] == '@generated:peer:0'  # Placeholder
        assert user_event['name'] == 'Alice'
        assert user_event['network_id'] == 'test_network'
        assert user_event['group_id'] == 'test_group'
        assert 'invite_pubkey' in user_event
        assert 'invite_signature' in user_event

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_as_user_placeholder_resolution(self):
        """Test that join_as_user uses placeholders correctly."""
        invite_data = {
            'invite_secret': 'test_secret',
            'network_id': 'test_network',
            'group_id': 'test_group'
        }
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            'invite_link': invite_link,
            'name': 'Bob',
            '_db': self.db
        }

        envelopes = join_as_user(params)

        # Check that user event references peer with placeholder
        user_env = envelopes[2]
        user_event = user_env['event_plaintext']
        assert user_event['peer_id'] == '@generated:peer:0'

        # Check that user deps include placeholder
        assert '@generated:peer:0' in user_env['deps']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_as_user_invalid_invite_link(self):
        """Test that join_as_user handles invalid invite links."""
        # Test invalid prefix
        with pytest.raises(ValueError, match="Invalid invite link format"):
            join_as_user({
                'invite_link': 'invalid://invite/abc',
                'name': 'Alice',
                '_db': self.db
            })

        # Test invalid base64
        with pytest.raises(ValueError, match="Invalid invite link encoding"):
            join_as_user({
                'invite_link': 'quiet://invite/not_base64!!!',
                'name': 'Alice',
                '_db': self.db
            })

        # Test missing fields in invite data
        invalid_invite_data = {'network_id': 'test'}  # Missing invite_secret and group_id
        invite_json = json.dumps(invalid_invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        with pytest.raises(ValueError, match="Invalid invite data"):
            join_as_user({
                'invite_link': invite_link,
                'name': 'Alice',
                '_db': self.db
            })

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_as_user_generates_name(self):
        """Test that join_as_user generates name if not provided."""
        invite_data = {
            'invite_secret': 'test_secret',
            'network_id': 'test_network',
            'group_id': 'test_group'
        }
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            'invite_link': invite_link,
            # No name provided
            '_db': self.db
        }

        envelopes = join_as_user(params)

        # Check that a name was generated
        user_env = envelopes[2]
        user_event = user_env['event_plaintext']
        assert 'name' in user_event
        assert user_event['name'].startswith('User-')  # Generated names start with User-

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_as_user_database_storage(self):
        """Test that join_as_user stores identity in database."""
        invite_data = {
            'invite_secret': 'test_secret',
            'network_id': 'test_network',
            'group_id': 'test_group'
        }
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"

        params = {
            'invite_link': invite_link,
            'name': 'Charlie',
            '_db': self.db
        }

        envelopes = join_as_user(params)
        identity_env = envelopes[0]
        identity_id = identity_env['event_id']

        # Check that identity was stored in core_identities
        cursor = self.db.execute(
            "SELECT * FROM core_identities WHERE identity_id = ?",
            (identity_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['name'] == 'Charlie'
        assert row['private_key'] is not None