"""
Tests for group commands.
"""
import pytest
import tempfile
import os
from protocols.quiet.events.group.commands import create_group
from core.db import get_connection, init_database


class TestGroupCommands:
    """Test group commands."""

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
    def test_create_group_envelope_structure(self):
        """Test that create_group generates correct envelope structure."""
        params = {
            'name': 'My Group',
            'network_id': self.network_id,
            'peer_id': self.peer_id
        }

        envelopes = create_group(params)

        # Should return a list with one envelope (group only)
        assert len(envelopes) == 1

        envelope = envelopes[0]

        # Check envelope structure
        assert envelope['event_type'] == 'group'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == self.peer_id
        assert envelope['network_id'] == self.network_id

        # Check dependencies (group has no dependencies)
        assert envelope['deps'] == []

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'group'
        assert event['group_id'] == ''  # Will be filled by encrypt handler
        assert event['name'] == 'My Group'
        assert event['network_id'] == self.network_id
        assert event['creator_id'] == self.peer_id
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_no_dependencies(self):
        """Test that create_group has no dependencies."""
        params = {
            'name': 'Test Group',
            'network_id': self.network_id,
            'peer_id': self.peer_id
        }

        envelopes = create_group(params)
        envelope = envelopes[0]

        # Group should have no dependencies
        assert envelope['deps'] == []

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_missing_peer_id(self):
        """Test that create_group requires peer_id."""
        params = {
            'name': 'My Group',
            'network_id': self.network_id
            # Missing peer_id
        }

        with pytest.raises(ValueError, match="peer_id is required"):
            create_group(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_default_name(self):
        """Test that create_group uses default name if not provided."""
        params = {
            # No name
            'network_id': self.network_id,
            'peer_id': self.peer_id
        }

        envelopes = create_group(params)
        envelope = envelopes[0]

        event = envelope['event_plaintext']
        assert event['name'] == 'unnamed-group'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_empty_name(self):
        """Test that create_group handles empty name."""
        params = {
            'name': '',  # Empty name
            'network_id': self.network_id,
            'peer_id': self.peer_id
        }

        envelopes = create_group(params)
        envelope = envelopes[0]

        event = envelope['event_plaintext']
        assert event['name'] == 'unnamed-group'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_default_network(self):
        """Test that create_group uses default network if not provided."""
        params = {
            'name': 'My Group',
            # No network_id
            'peer_id': self.peer_id
        }

        envelopes = create_group(params)
        envelope = envelopes[0]

        event = envelope['event_plaintext']
        assert event['network_id'] == 'dummy-network-id'
        assert envelope['network_id'] == 'dummy-network-id'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_timestamp(self):
        """Test that create_group includes timestamp."""
        params = {
            'name': 'My Group',
            'network_id': self.network_id,
            'peer_id': self.peer_id
        }

        envelopes = create_group(params)
        envelope = envelopes[0]

        event = envelope['event_plaintext']
        assert 'created_at' in event
        assert isinstance(event['created_at'], int)
        assert event['created_at'] > 0

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_returns_list(self):
        """Test that create_group returns a list of envelopes."""
        params = {
            'name': 'My Group',
            'network_id': self.network_id,
            'peer_id': self.peer_id
        }

        result = create_group(params)

        # Should return a list
        assert isinstance(result, list)
        assert len(result) == 1  # Only group event now (member created separately)