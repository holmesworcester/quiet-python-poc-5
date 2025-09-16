"""
Tests for network event type command (create).
"""
import pytest
import tempfile
import os
from protocols.quiet.events.network.commands import create_network
from protocols.quiet.events.peer.commands import create_peer
from core.db import get_connection, init_database
from core.identity import create_identity as create_core_identity


class TestNetworkCommand:
    """Test network creation command."""

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

        # Create a test identity and peer for use in tests
        self.identity = create_core_identity('Test Creator', db_path=self.db_path)
        self.peer_params = {
            'identity_id': self.identity.id,
            'username': 'TestCreator',
            '_db': self.db
        }
        self.peer_envelope = create_peer(self.peer_params)
        # Simulate that peer is already created (would be done by pipeline)
        self.peer_id = 'test_peer_id'  # In reality, this would be generated

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_basic(self):
        """Test basic network creation."""
        params = {
            "name": "Test Network",
            "peer_id": self.peer_id
        }

        envelope = create_network(params)

        # Should return a single envelope
        assert envelope is not None
        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "network"
        assert envelope["self_created"] == True

        # Check network event content
        network_event = envelope["event_plaintext"]
        assert network_event["type"] == "network"
        assert network_event["name"] == "Test Network"
        assert network_event["network_id"] == ''  # Will be filled by crypto handler
        assert network_event["creator_id"] == self.peer_id
        assert "created_at" in network_event
        assert network_event["signature"] == ''  # Will be filled by sign handler

        # Check dependencies
        assert envelope["deps"] == [f'peer:{self.peer_id}']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_with_identity_id(self):
        """Test network creation with identity_id (backward compat)."""
        params = {
            "name": "Test Network",
            "identity_id": self.identity.id  # Using identity_id instead of peer_id
        }

        envelope = create_network(params)

        # Should still work with identity_id
        network_event = envelope["event_plaintext"]
        assert network_event["creator_id"] == self.identity.id

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_missing_name(self):
        """Test that missing name raises error."""
        params = {
            "peer_id": self.peer_id
            # Missing name
        }

        with pytest.raises(ValueError, match="name is required"):
            create_network(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_empty_name(self):
        """Test that empty name raises error."""
        params = {
            "name": "",
            "peer_id": self.peer_id
        }

        with pytest.raises(ValueError, match="name is required"):
            create_network(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_missing_peer_id(self):
        """Test that missing peer_id raises error."""
        params = {
            "name": "Test Network"
            # Missing peer_id
        }

        with pytest.raises(ValueError, match="peer_id is required"):
            create_network(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_envelope_structure(self):
        """Test the structure of the envelope returned by create_network."""
        params = {
            "name": "My Network",
            "peer_id": self.peer_id
        }

        envelope = create_network(params)

        # Check all required envelope fields
        assert envelope["event_type"] == "network"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == self.peer_id
        assert envelope["network_id"] == ''  # Empty initially
        assert envelope["deps"] == [f'peer:{self.peer_id}']

        # Check event plaintext structure
        event = envelope["event_plaintext"]
        assert event["type"] == "network"
        assert event["network_id"] == ''
        assert event["name"] == "My Network"
        assert event["creator_id"] == self.peer_id
        assert isinstance(event["created_at"], int)
        assert event["signature"] == ''