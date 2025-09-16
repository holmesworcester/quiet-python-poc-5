"""
Tests for channel commands.
"""
import pytest
import tempfile
import os
from protocols.quiet.events.channel.commands import create_channel
from core.db import get_connection, init_database


class TestChannelCommands:
    """Test channel commands."""

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
        self.group_id = 'test_group_id'
        self.network_id = 'test_network_id'

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_envelope_structure(self):
        """Test that create_channel generates correct envelope structure."""
        params = {
            'name': 'general',
            'group_id': self.group_id,
            'peer_id': self.peer_id,
            'network_id': self.network_id
        }

        envelope = create_channel(params)

        # Check envelope structure
        assert envelope['event_type'] == 'channel'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == self.peer_id
        assert envelope['network_id'] == self.network_id

        # Check dependencies
        assert envelope['deps'] == [f"group:{self.group_id}"]

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'channel'
        assert event['channel_id'] == ''  # Will be filled by encrypt handler
        assert event['group_id'] == self.group_id
        assert event['name'] == 'general'
        assert event['network_id'] == self.network_id
        assert event['creator_id'] == self.peer_id
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_dependency(self):
        """Test that create_channel depends on group."""
        params = {
            'name': 'test-channel',
            'group_id': 'group_123',
            'peer_id': self.peer_id,
            'network_id': self.network_id
        }

        envelope = create_channel(params)

        # Should depend only on group
        assert len(envelope['deps']) == 1
        assert envelope['deps'][0] == "group:group_123"

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_missing_peer_id(self):
        """Test that create_channel requires peer_id."""
        params = {
            'name': 'general',
            'group_id': self.group_id,
            'network_id': self.network_id
            # Missing peer_id
        }

        with pytest.raises(ValueError, match="peer_id is required"):
            create_channel(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_default_name(self):
        """Test that create_channel uses default name if not provided."""
        params = {
            # No name
            'group_id': self.group_id,
            'peer_id': self.peer_id,
            'network_id': self.network_id
        }

        envelope = create_channel(params)

        event = envelope['event_plaintext']
        assert event['name'] == 'unnamed-channel'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_empty_name(self):
        """Test that create_channel handles empty name."""
        params = {
            'name': '',  # Empty name
            'group_id': self.group_id,
            'peer_id': self.peer_id,
            'network_id': self.network_id
        }

        envelope = create_channel(params)

        event = envelope['event_plaintext']
        assert event['name'] == 'unnamed-channel'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_default_group(self):
        """Test that create_channel uses default group if not provided."""
        params = {
            'name': 'general',
            # No group_id
            'peer_id': self.peer_id,
            'network_id': self.network_id
        }

        envelope = create_channel(params)

        event = envelope['event_plaintext']
        assert event['group_id'] == 'dummy-group-id'
        assert envelope['deps'] == ['group:dummy-group-id']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_default_network(self):
        """Test that create_channel uses default network if not provided."""
        params = {
            'name': 'general',
            'group_id': self.group_id,
            'peer_id': self.peer_id
            # No network_id
        }

        envelope = create_channel(params)

        event = envelope['event_plaintext']
        assert event['network_id'] == 'dummy-network-id'
        assert envelope['network_id'] == 'dummy-network-id'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_channel_timestamp(self):
        """Test that create_channel includes timestamp."""
        params = {
            'name': 'general',
            'group_id': self.group_id,
            'peer_id': self.peer_id,
            'network_id': self.network_id
        }

        envelope = create_channel(params)

        event = envelope['event_plaintext']
        assert 'created_at' in event
        assert isinstance(event['created_at'], int)
        assert event['created_at'] > 0