"""
Tests for address commands.
"""
import pytest
import tempfile
import os
from protocols.quiet.events.address.commands import announce_address, create_address_add, create_address_remove
from core.db import get_connection, init_database


class TestAddressCommands:
    """Test address commands."""

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

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_announce_address_envelope_structure(self):
        """Test that announce_address generates correct envelope structure."""
        params = {
            'peer_id': self.peer_id,
            'ip': '192.168.1.100',
            'port': 8080,
            'action': 'add',
            'network_id': self.network_id
        }

        envelope = announce_address(params)

        # Check envelope structure
        assert envelope['event_type'] == 'address'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == self.peer_id
        assert envelope['network_id'] == self.network_id

        # Check dependencies
        assert envelope['deps'] == [f"peer:{self.peer_id}"]

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'address'
        assert event['action'] == 'add'
        assert event['peer_id'] == self.peer_id
        assert event['ip'] == '192.168.1.100'
        assert event['port'] == 8080
        assert event['network_id'] == self.network_id
        assert 'timestamp_ms' in event
        assert event['signature'] == ''  # Not signed yet

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_announce_address_default_values(self):
        """Test that announce_address uses default values."""
        params = {
            'peer_id': self.peer_id,
            # Minimal parameters
        }

        envelope = announce_address(params)

        event = envelope['event_plaintext']
        assert event['ip'] == '127.0.0.1'  # Default IP
        assert event['port'] == 5000  # Default port
        assert event['action'] == 'add'  # Default action
        assert event['network_id'] == ''  # Default empty network_id

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_announce_address_remove_action(self):
        """Test announce_address with remove action."""
        params = {
            'peer_id': self.peer_id,
            'ip': '10.0.0.1',
            'port': 9999,
            'action': 'remove',
            'network_id': self.network_id
        }

        envelope = announce_address(params)

        event = envelope['event_plaintext']
        assert event['action'] == 'remove'
        assert event['ip'] == '10.0.0.1'
        assert event['port'] == 9999

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_address_add(self):
        """Test create_address_add helper function."""
        envelope = create_address_add(
            peer_id=self.peer_id,
            ip='192.168.1.50',
            port=7777,
            network_id=self.network_id
        )

        assert envelope['event_type'] == 'address'
        event = envelope['event_plaintext']
        assert event['action'] == 'add'
        assert event['peer_id'] == self.peer_id
        assert event['ip'] == '192.168.1.50'
        assert event['port'] == 7777
        assert event['network_id'] == self.network_id

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_address_remove(self):
        """Test create_address_remove helper function."""
        envelope = create_address_remove(
            peer_id=self.peer_id,
            ip='192.168.1.50',
            port=7777,
            network_id=self.network_id
        )

        assert envelope['event_type'] == 'address'
        event = envelope['event_plaintext']
        assert event['action'] == 'remove'
        assert event['peer_id'] == self.peer_id
        assert event['ip'] == '192.168.1.50'
        assert event['port'] == 7777
        assert event['network_id'] == self.network_id

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_announce_address_timestamp(self):
        """Test that announce_address includes timestamp."""
        params = {
            'peer_id': self.peer_id,
            'ip': '192.168.1.1',
            'port': 5555
        }

        envelope = announce_address(params)

        event = envelope['event_plaintext']
        assert 'timestamp_ms' in event
        assert isinstance(event['timestamp_ms'], int)
        assert event['timestamp_ms'] > 0

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_announce_address_port_conversion(self):
        """Test that port is converted to int."""
        params = {
            'peer_id': self.peer_id,
            'port': '8080'  # String port
        }

        envelope = announce_address(params)

        event = envelope['event_plaintext']
        assert event['port'] == 8080
        assert isinstance(event['port'], int)