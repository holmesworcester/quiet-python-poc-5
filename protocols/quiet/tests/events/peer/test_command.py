"""
Tests for peer commands.
"""
import pytest
import tempfile
import os
from protocols.quiet.events.peer.commands import create_peer
from core.db import get_connection, init_database
from core.identity import create_identity as create_core_identity


class TestPeerCommands:
    """Test peer commands."""

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

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_peer_envelope_structure(self):
        """Test that create_peer generates correct envelope structure."""
        # First create an identity
        identity = create_core_identity('Test User', db_path=self.db_path)
        identity_id = identity.id

        params = {
            'identity_id': identity_id,
            'username': 'TestUser',
            '_db': self.db
        }

        envelope = create_peer(params)

        # Check envelope structure
        assert envelope['event_type'] == 'peer'
        assert envelope['self_created'] == True
        # Peer envelope is network-agnostic
        assert envelope['deps'] == []  # No dependencies

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'peer'
        assert event['peer_id'] == ''  # Will be filled by crypto handler
        assert event['public_key'] == identity.public_key.hex()
        assert event['identity_id'] == identity_id
        # Peer event has no network_id
        assert event['username'] == 'TestUser'
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_peer_missing_identity(self):
        """Test that create_peer fails without identity_id."""
        params = {
            'username': 'TestUser',
            'network_id': 'test_network',
            '_db': self.db
        }

        with pytest.raises(ValueError, match="identity_id is required"):
            create_peer(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_peer_nonexistent_identity(self):
        """Test that create_peer fails with nonexistent identity."""
        params = {
            'identity_id': 'nonexistent',
            'username': 'TestUser',
            'network_id': 'test_network',
            '_db': self.db
        }

        with pytest.raises(ValueError, match="Identity nonexistent not found"):
            create_peer(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_peer_default_username(self):
        """Test that create_peer uses default username if not provided."""
        # First create an identity
        identity = create_core_identity('Test User', db_path=self.db_path)
        identity_id = identity.id

        params = {
            'identity_id': identity_id,
            # No username provided
            'network_id': 'test_network',
            '_db': self.db
        }

        envelope = create_peer(params)

        # Check that default username is used
        event = envelope['event_plaintext']
        assert event['username'] == 'User'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_peer_empty_network_id(self):
        """Test that create_peer allows empty network_id initially."""
        # First create an identity
        identity = create_core_identity('Test User', db_path=self.db_path)
        identity_id = identity.id

        params = {
            'identity_id': identity_id,
            'username': 'TestUser',
            '_db': self.db
        }

        envelope = create_peer(params)

        # No network_id on peer event or envelope
        event = envelope['event_plaintext']
        assert 'network_id' not in event
        assert 'network_id' not in envelope
