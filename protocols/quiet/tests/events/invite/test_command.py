"""
Tests for invite commands.
"""
import pytest
import tempfile
import os
import base64
import json
from protocols.quiet.events.invite.commands import create_invite
from core.db import get_connection, init_database


class TestInviteCommands:
    """Test invite commands."""

    def setup_method(self):
        """Set up test database."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        self.db = get_connection(self.db_path)

        # Get the protocol directory properly
        import pathlib
        test_dir = pathlib.Path(__file__).parent
        protocol_dir = test_dir.parent.parent.parent
        init_database(self.db, str(protocol_dir))

        # Set up test data
        self.peer_id = 'test_peer_id'
        self.network_id = 'test_network_id'
        self.group_id = 'test_group_id'

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_envelope_structure(self):
        """Test that create_invite generates correct envelope structure."""
        params = {
            'peer_id': self.peer_id,
            'network_id': self.network_id,
            'group_id': self.group_id
        }

        envelope = create_invite(params)

        # Check envelope structure
        assert envelope['event_type'] == 'invite'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == self.peer_id
        assert envelope['network_id'] == self.network_id

        # Check dependencies
        assert envelope['deps'] == [f"group:{self.group_id}"]

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'invite'
        assert event['inviter_id'] == self.peer_id
        assert event['network_id'] == self.network_id
        assert event['group_id'] == self.group_id
        assert 'invite_pubkey' in event
        assert 'invite_secret' in event
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet

        # Check invite link
        assert 'invite_link' in envelope
        assert envelope['invite_link'].startswith('quiet://invite/')
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_peer_id(self):
        """Test that create_invite requires peer_id."""
        params = {
            'network_id': self.network_id,
            'group_id': self.group_id
            # Missing peer_id
        }

        with pytest.raises(ValueError, match="peer_id is required"):
            create_invite(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_default_values(self):
        """Test that create_invite uses default values."""
        params = {
            'peer_id': self.peer_id
            # Minimal parameters
        }

        envelope = create_invite(params)

        event = envelope['event_plaintext']
        assert event['network_id'] == ''  # Default empty
        assert event['group_id'] == ''  # Default empty

        # Check dependencies with empty group_id
        assert envelope['deps'] == ['group:']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_link_format(self):
        """Test that invite link has correct format."""
        params = {
            'peer_id': self.peer_id,
            'network_id': self.network_id,
            'group_id': self.group_id
        }

        envelope = create_invite(params)

        # Parse invite link
        assert envelope['invite_link'].startswith('quiet://invite/')
        link_data = envelope['invite_link'][len('quiet://invite/'):]

        # Decode base64
        decoded = base64.b64decode(link_data)
        invite_data = json.loads(decoded)

        # Check invite data structure
        assert 'invite_secret' in invite_data
        assert invite_data['network_id'] == self.network_id
        assert invite_data['group_id'] == self.group_id

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_unique_secrets(self):
        """Test that each invite has unique secrets."""
        params = {
            'peer_id': self.peer_id,
            'network_id': self.network_id,
            'group_id': self.group_id
        }

        # Create two invites
        envelope1 = create_invite(params)
        envelope2 = create_invite(params)

        event1 = envelope1['event_plaintext']
        event2 = envelope2['event_plaintext']

        # Each invite should have different secrets and pubkeys
        assert event1['invite_secret'] != event2['invite_secret']
        assert event1['invite_pubkey'] != event2['invite_pubkey']
        assert envelope1['invite_link'] != envelope2['invite_link']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_timestamp(self):
        """Test that create_invite includes timestamp."""
        params = {
            'peer_id': self.peer_id,
            'network_id': self.network_id,
            'group_id': self.group_id
        }

        envelope = create_invite(params)

        event = envelope['event_plaintext']
        assert 'created_at' in event
        assert isinstance(event['created_at'], int)
        assert event['created_at'] > 0

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_dependency(self):
        """Test that create_invite depends on group."""
        params = {
            'peer_id': self.peer_id,
            'network_id': self.network_id,
            'group_id': 'group_123'
        }

        envelope = create_invite(params)

        # Should depend only on group
        assert len(envelope['deps']) == 1
        assert envelope['deps'][0] == 'group:group_123'